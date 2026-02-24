from odoo import fields, models, api
import json


class SaleTemplateTagFilter(models.Model):
    _name = 'sale.template.tag.filter'
    _order = 'sequence, name'

    name = fields.Char(required=True, string="Nombre")
    rotation_field = fields.Char(string="Campo Roturador")
    sequence = fields.Integer(default=10)
    first_selection = fields.Boolean(string="Primera Selección")
    parent_tag_id = fields.Many2many(
        'sale.template.tag.filter',
        'sale_tmpl_tag_filter_parent_rel',
        'child_id', 'parent_id',
        string="Tag Padre",
    )


class SaleTemplateLineTagConfig(models.Model):
    _name = 'sale.template.line.tag.config'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    tag_filter_id = fields.Many2one('sale.template.tag.filter', required=True, string="Etiqueta")
    template_line_id = fields.Many2one('sale.order.template.line', ondelete='cascade')
    domain = fields.Char(string="Dominio Producto", default='[]')


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    tag_filter_ids = fields.Many2many(
        'sale.template.tag.filter',
        'sale_order_template_tag_filter_rel',
        'template_id', 'tag_filter_id',
        string="Etiquetas de Configuración",
    )


class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    tag_config_ids = fields.One2many(
        'sale.template.line.tag.config',
        'template_line_id',
        string="Config Etiquetas",
        copy=True,
    )

    def open_tag_config(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Configuración Etiquetas',
            'res_model': 'sale.template.line.tag.config',
            'view_mode': 'tree,form',
            'domain': [('template_line_id', '=', self.id)],
            'context': {
                'default_template_line_id': self.id,
            },
            'target': 'new',
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_config_tag_ids = fields.Many2many(
        'sale.template.tag.filter',
        'sale_order_config_tag_rel',
        'order_id', 'tag_id',
        string="Etiquetas de Configuración",
    )
    select_config_tag_id = fields.Many2one(
        'sale.template.tag.filter',
        string="Seleccionar etiqueta de config",
    )
    selected_config_tags_name = fields.Char(
        compute='_compute_selected_config_tags_name',
        string="Etiquetas config seleccionadas",
    )
    config_tag_domain = fields.Char(compute='_compute_config_tag_domain')
    config_tag_order = fields.Char(default='[]', copy=False)

    @api.onchange('select_config_tag_id')
    def _onchange_select_config_tag_id(self):
        if self.select_config_tag_id:
            tag_id = self.select_config_tag_id.id
            self.sale_config_tag_ids = [(4, tag_id)]
            order = json.loads(self.config_tag_order or '[]')
            if tag_id not in order:
                order.append(tag_id)
            self.config_tag_order = json.dumps(order)
            self.select_config_tag_id = False

    def undo_last_config_tag(self):
        self.ensure_one()
        order = json.loads(self.config_tag_order or '[]')
        if not order:
            return True
        last_tag_id = order.pop()
        cr = self.env.cr
        cr.execute(
            "UPDATE sale_order SET config_tag_order = %s WHERE id = %s",
            (json.dumps(order), self.id)
        )
        cr.execute("""
            DELETE FROM sale_order_config_tag_rel
            WHERE order_id = %s AND tag_id = %s
        """, (self.id, last_tag_id))
        self.invalidate_cache()
        return True

    def clear_all_config_tags(self):
        self.ensure_one()
        cr = self.env.cr
        cr.execute(
            "UPDATE sale_order SET config_tag_order = '[]' WHERE id = %s",
            (self.id,)
        )
        cr.execute(
            "DELETE FROM sale_order_config_tag_rel WHERE order_id = %s",
            (self.id,)
        )
        self.invalidate_cache()
        return True

    @api.depends('sale_config_tag_ids', 'config_tag_order')
    def _compute_selected_config_tags_name(self):
        for r in self:
            order = json.loads(r.config_tag_order or '[]')
            if order:
                tags = self.env['sale.template.tag.filter'].browse(order).exists()
                tag_map = {t.id: t.name for t in tags}
                r.selected_config_tags_name = ' | '.join(
                    tag_map[tid] for tid in order if tid in tag_map
                )
            elif r.sale_config_tag_ids:
                r.selected_config_tags_name = ' | '.join(r.sale_config_tag_ids.mapped('name'))
            else:
                r.selected_config_tags_name = ''

    @api.depends('sale_config_tag_ids', 'sale_order_template_id', 'config_tag_order')
    def _compute_config_tag_domain(self):
        for r in self:
            if not r.sale_order_template_id or not r.sale_order_template_id.tag_filter_ids:
                r.config_tag_domain = json.dumps([('id', '=', 0)])
                continue
            res = [('id', 'in', r.sale_order_template_id.tag_filter_ids.ids)]
            order = json.loads(r.config_tag_order or '[]')
            if order:
                last_tag_id = order[-1]
                res.append(('parent_tag_id', 'in', [last_tag_id]))
            elif r.sale_config_tag_ids:
                last_tag = r.sale_config_tag_ids[-1]
                res.append(('parent_tag_id', 'in', [last_tag.id]))
            else:
                res.append(('first_selection', '=', True))
            r.config_tag_domain = json.dumps(res)

    def apply_config_tags(self):
        self.ensure_one()
        cr = self.env.cr

        # 1. Get selected config tag IDs via SQL
        cr.execute(
            "SELECT tag_id FROM sale_order_config_tag_rel WHERE order_id = %s",
            (self.id,)
        )
        config_tag_ids = tuple(r[0] for r in cr.fetchall())
        if not config_tag_ids:
            return True

        # 2. Single SQL JOIN: line + template_line + tag_config data
        cr.execute("""
            SELECT sol.id, sotl.alternative_product_domain, stltc.domain
            FROM sale_order_line sol
            JOIN sale_order_template_line sotl ON sotl.id = sol.sale_template_line_id
            JOIN sale_template_line_tag_config stltc ON stltc.template_line_id = sotl.id
            WHERE sol.order_id = %s
              AND sol.sale_template_line_id IS NOT NULL
              AND stltc.tag_filter_id IN %s
        """, (self.id, config_tag_ids))
        rows = cr.fetchall()
        if not rows:
            return True

        # 3. Group lines by computed domain
        line_domains = {}
        for line_id, alt_domain, config_domain in rows:
            if line_id not in line_domains:
                line_domains[line_id] = json.loads(alt_domain or '[]')
            line_domains[line_id].extend(json.loads(config_domain or '[]'))

        domain_to_lines = {}
        for line_id, domain in line_domains.items():
            if not domain:
                continue
            key = json.dumps(domain, sort_keys=True)
            domain_to_lines.setdefault(key, {'domain': domain, 'line_ids': []})
            domain_to_lines[key]['line_ids'].append(line_id)

        if not domain_to_lines:
            return True

        # 4. One product search per unique domain + SQL update
        updated_count = 0
        all_updated_ids = []
        for entry in domain_to_lines.values():
            product = self.env['product.product'].search(entry['domain'], limit=1)
            if not product:
                continue
            name = product.get_product_multiline_description_sale()
            line_ids = tuple(entry['line_ids'])
            cr.execute("""
                UPDATE sale_order_line
                SET product_id = %s, price_unit = %s, name = %s
                WHERE id IN %s
            """, (product.id, product.lst_price, name, line_ids))
            updated_count += len(line_ids)
            all_updated_ids.extend(line_ids)

        # 5. Trigger recompute of stored computed fields (price_subtotal, etc.)
        if updated_count:
            self.invalidate_cache()
            updated_lines = self.env['sale.order.line'].browse(all_updated_ids)
            updated_lines.modified(['product_id', 'price_unit', 'name'])

        # 6. Chatter via SQL
        cr.execute("""
            SELECT t.name FROM sale_order_config_tag_rel r
            JOIN sale_template_tag_filter t ON t.id = r.tag_id
            WHERE r.order_id = %s ORDER BY t.sequence, t.name
        """, (self.id,))
        tag_names = ', '.join(r[0] for r in cr.fetchall())
        self.message_post(
            body="Configuración de etiquetas aplicada: <b>%s</b>. %d línea(s) actualizada(s)." % (tag_names, updated_count),
        )
        return True
