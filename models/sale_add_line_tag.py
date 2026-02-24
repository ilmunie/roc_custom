from odoo import fields, models, api
import json


class SaleOrderLineAddTag(models.Model):
    _name = 'sale.order.line.add.tag'
    _order = 'sequence, name'

    name = fields.Char(required=True, string="Nombre")
    sequence = fields.Integer(default=10, string="Secuencia")
    product_id = fields.Many2one('product.product', required=True, string="Producto")
    price_method = fields.Selection([
        ('fixed_amount', 'Monto Fijo'),
        ('lst_price', 'Precio Lista Producto'),
        ('percentage', 'Porcentaje'),
    ], required=True, default='fixed_amount', string="Método de Cálculo")
    fixed_amount = fields.Float(string="Monto Fijo")
    percentage_value = fields.Float(string="Porcentaje (%)")
    tax_type = fields.Selection([
        ('with_tax', 'Con Impuestos'),
        ('without_tax', 'Sin Impuestos'),
    ], default='without_tax', string="Base de Cálculo")
    product_domain = fields.Char(
        string="Dominio Productos (filtro %)",
        default='[]',
        help="Si se establece, solo las líneas con productos que cumplan este dominio son incluidas en el cálculo del porcentaje.",
    )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    line_add_tag_ids = fields.Many2many(
        'sale.order.line.add.tag',
        'sale_order_add_tag_rel',
        'order_id', 'tag_id',
        string="Etiquetas de Línea Extra",
    )
    select_add_tag_id = fields.Many2one(
        'sale.order.line.add.tag',
        string="Agregar etiqueta de línea",
    )
    selected_add_tags_name = fields.Char(
        compute='_compute_selected_add_tags_name',
        string="Etiquetas línea seleccionadas",
    )
    add_tag_exclude_domain = fields.Char(compute='_compute_add_tag_exclude_domain')
    add_tag_order = fields.Char(default='[]', copy=False)

    @api.onchange('select_add_tag_id')
    def _onchange_select_add_tag_id(self):
        if self.select_add_tag_id:
            tag_id = self.select_add_tag_id.id
            self.line_add_tag_ids = [(4, tag_id)]
            order = json.loads(self.add_tag_order or '[]')
            if tag_id not in order:
                order.append(tag_id)
            self.add_tag_order = json.dumps(order)
            self.select_add_tag_id = False

    def undo_last_add_tag(self):
        self.ensure_one()
        order = json.loads(self.add_tag_order or '[]')
        if not order:
            return True
        last_tag_id = order.pop()
        cr = self.env.cr
        cr.execute(
            "UPDATE sale_order SET add_tag_order = %s WHERE id = %s",
            (json.dumps(order), self.id)
        )
        cr.execute("""
            DELETE FROM sale_order_add_tag_rel
            WHERE order_id = %s AND tag_id = %s
        """, (self.id, last_tag_id))
        self.invalidate_cache()
        return True

    def clear_all_add_tags(self):
        self.ensure_one()
        cr = self.env.cr
        cr.execute(
            "UPDATE sale_order SET add_tag_order = '[]' WHERE id = %s",
            (self.id,)
        )
        cr.execute(
            "DELETE FROM sale_order_add_tag_rel WHERE order_id = %s",
            (self.id,)
        )
        self.invalidate_cache()
        return True

    @api.depends('line_add_tag_ids', 'add_tag_order')
    def _compute_selected_add_tags_name(self):
        for r in self:
            order = json.loads(r.add_tag_order or '[]')
            if order:
                tags = self.env['sale.order.line.add.tag'].browse(order).exists()
                tag_map = {t.id: t.name for t in tags}
                r.selected_add_tags_name = ' | '.join(
                    tag_map[tid] for tid in order if tid in tag_map
                )
            elif r.line_add_tag_ids:
                r.selected_add_tags_name = ' | '.join(
                    r.line_add_tag_ids.sorted('sequence').mapped('name')
                )
            else:
                r.selected_add_tags_name = ''

    @api.depends('line_add_tag_ids')
    def _compute_add_tag_exclude_domain(self):
        for r in self:
            excluded = r.line_add_tag_ids.ids
            if excluded:
                r.add_tag_exclude_domain = json.dumps([('id', 'not in', excluded)])
            else:
                r.add_tag_exclude_domain = json.dumps([])

    def apply_add_tags(self):
        self.ensure_one()
        cr = self.env.cr

        # 1. Get selected tags data via SQL (one query)
        cr.execute("""
            SELECT t.id, t.name, t.sequence, t.product_id, t.price_method,
                   t.fixed_amount, t.percentage_value, t.tax_type, t.product_domain,
                   pt.list_price, pt.name as product_name, pt.uom_id
            FROM sale_order_add_tag_rel r
            JOIN sale_order_line_add_tag t ON t.id = r.tag_id
            JOIN product_product p ON p.id = t.product_id
            JOIN product_template pt ON pt.id = p.product_tmpl_id
            WHERE r.order_id = %s
            ORDER BY t.sequence, t.name
        """, (self.id,))
        tags_data = cr.fetchall()
        selected_tag_ids = tuple(t[0] for t in tags_data) if tags_data else ()

        # 2. Remove lines whose tag is no longer selected (SQL)
        if selected_tag_ids:
            cr.execute("""
                DELETE FROM sale_order_line
                WHERE order_id = %s AND add_tag_id IS NOT NULL
                  AND add_tag_id NOT IN %s
            """, (self.id, selected_tag_ids))
        else:
            cr.execute("""
                DELETE FROM sale_order_line
                WHERE order_id = %s AND add_tag_id IS NOT NULL
            """, (self.id,))

        if not tags_data:
            self.invalidate_cache()
            return True

        # 3. Get existing add_tag line mapping via SQL
        cr.execute("""
            SELECT add_tag_id, id FROM sale_order_line
            WHERE order_id = %s AND add_tag_id IS NOT NULL
        """, (self.id,))
        existing_map = dict(cr.fetchall())

        # 4. Process each tag - calculate prices
        domain_cache = {}
        to_create = []
        to_update = []
        tag_names = []

        for (tag_id, tag_name, tag_seq, product_id, price_method,
             fixed_amount, pct_value, tax_type, product_domain,
             lst_price, product_name, uom_id) in tags_data:

            tag_names.append(tag_name)

            if price_method == 'fixed_amount':
                price_unit = fixed_amount or 0.0
            elif price_method == 'lst_price':
                price_unit = lst_price or 0.0
            elif price_method == 'percentage':
                # Calculate base via SQL
                amount_col = 'price_total' if tax_type == 'with_tax' else 'price_subtotal'
                if product_domain and product_domain != '[]':
                    if product_domain not in domain_cache:
                        domain = json.loads(product_domain)
                        pids = self.env['product.product'].search(domain).ids
                        domain_cache[product_domain] = tuple(pids) if pids else (0,)
                    filter_ids = domain_cache[product_domain]
                    cr.execute("""
                        SELECT COALESCE(SUM(sol.{col}), 0)
                        FROM sale_order_line sol
                        WHERE sol.order_id = %s
                          AND (sol.add_tag_id IS NULL OR sol.add_tag_id IN (
                              SELECT id FROM sale_order_line_add_tag WHERE sequence < %s
                          ))
                          AND sol.product_id IN %s
                    """.format(col=amount_col), (self.id, tag_seq, filter_ids))
                else:
                    cr.execute("""
                        SELECT COALESCE(SUM(sol.{col}), 0)
                        FROM sale_order_line sol
                        WHERE sol.order_id = %s
                          AND (sol.add_tag_id IS NULL OR sol.add_tag_id IN (
                              SELECT id FROM sale_order_line_add_tag WHERE sequence < %s
                          ))
                    """.format(col=amount_col), (self.id, tag_seq))
                base = cr.fetchone()[0]
                price_unit = base * ((pct_value or 0.0) / 100.0)
            else:
                price_unit = 0.0

            if tag_id in existing_map:
                to_update.append((price_unit, existing_map[tag_id]))
            else:
                to_create.append({
                    'order_id': self.id,
                    'product_id': product_id,
                    'name': product_name,
                    'price_unit': price_unit,
                    'product_uom_qty': 1,
                    'product_uom': uom_id,
                    'add_tag_id': tag_id,
                })

        # 5. Batch update existing lines via SQL + trigger recompute
        if to_update:
            for price_unit, line_id in to_update:
                cr.execute(
                    "UPDATE sale_order_line SET price_unit = %s WHERE id = %s",
                    (price_unit, line_id)
                )
            self.invalidate_cache()
            updated_lines = self.env['sale.order.line'].browse(
                [lid for _, lid in to_update]
            )
            updated_lines.modified(['price_unit'])

        # 6. Batch create new lines (ORM for tax/subtotal computation)
        if to_create:
            self.env['sale.order.line'].with_context(
                skip_procurement=True
            ).create(to_create)

        self.invalidate_cache()

        # 7. Chatter
        self.message_post(
            body="Líneas de recargo/descuento calculadas: <b>%s</b>." % ', '.join(tag_names),
        )
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    add_tag_id = fields.Many2one('sale.order.line.add.tag', string="Etiqueta de Línea")
