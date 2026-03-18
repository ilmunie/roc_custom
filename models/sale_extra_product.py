from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_product_multiline_description_sale(self):
        """Si tiene description_sale, usarla como nombre base + atributos.
        Si no, usar display_name (que ya incluye atributos)."""
        desc = (self.description_sale or '').strip()
        if desc:
            attrs = self.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name'
            )
            if attrs:
                desc += ' (' + ', '.join(attrs) + ')'
            return desc
        return self.display_name

    def get_product_multiline_description_purchase(self):
        """Mismo criterio que venta pero con description_purchase."""
        desc = (self.description_purchase or '').strip()
        if desc:
            attrs = self.product_template_attribute_value_ids.mapped(
                'product_attribute_value_id.name'
            )
            if attrs:
                desc += ' (' + ', '.join(attrs) + ')'
            return desc
        return self.display_name


class SaleExtraProductConfig(models.Model):
    _name = 'sale.extra.product.config'
    _order = 'sequence'

    product_tmpl_id = fields.Many2one('product.template', ondelete='cascade')
    sequence = fields.Integer(default=10)
    quantity = fields.Float(string="Cantidad", default=1)
    description = fields.Text(string="Descripción para el cliente")
    usage_type = fields.Selection([
        ('data_extra', 'Dato Extra'),
        ('attribute_change', 'Cambio Atributo'),
        ('attribute_value_change', 'Cambio Valor Atributo'),
        ('product_extra', 'Producto Extra'),
        ('other_product', 'Reemplazo Producto'),
    ], required=True, string="Tipo de Uso")
    extra_product_id = fields.Many2one(
        'product.product',
        string="Producto",
    )
    attribute_id = fields.Many2one(
        'product.attribute',
        string="Atributo",
    )
    attribute_value_id = fields.Many2one(
        'product.template.attribute.value',
        string="Valor Atributo",
    )

    @api.onchange('usage_type')
    def _onchange_usage_type(self):
        if self.usage_type not in ('attribute_change', 'attribute_value_change'):
            self.attribute_id = False
            self.attribute_value_id = False
        if self.usage_type not in ('product_extra', 'other_product'):
            self.extra_product_id = False

    @api.onchange('extra_product_id')
    def _onchange_extra_product_id(self):
        if self.extra_product_id and self.usage_type in ('product_extra', 'other_product'):
            self.description = self.extra_product_id.get_product_multiline_description_sale()

    @api.onchange('attribute_id')
    def _onchange_attribute_id(self):
        self.attribute_value_id = False
        if self.attribute_id and self.product_tmpl_id:
            attr_line = self.product_tmpl_id.attribute_line_ids.filtered(
                lambda l: l.attribute_id == self.attribute_id
            )
            if attr_line:
                return {'domain': {'attribute_value_id': [('id', 'in', attr_line.product_template_value_ids.ids)]}}
        return {'domain': {'attribute_value_id': [('id', '=', 0)]}}

    @api.onchange('attribute_value_id')
    def _onchange_attribute_value_id(self):
        if self.attribute_value_id and self.usage_type == 'attribute_value_change':
            val_name = self.attribute_value_id.product_attribute_value_id.name
            attr_name = self.attribute_id.name if self.attribute_id else ''
            price = self.attribute_value_id.price_extra
            if price:
                self.description = f"Cambio {attr_name} a {val_name}: +{price:.2f} €"
            else:
                self.description = f"Cambio {attr_name} a {val_name}"

    def get_price_display(self, current_product=None):
        """Returns the price text to show in the PDF for this config."""
        self.ensure_one()
        if self.usage_type == 'data_extra':
            return ''
        elif self.usage_type == 'attribute_change':
            # Show all values for this attribute with their price_extra
            if not self.attribute_id or not self.product_tmpl_id:
                return ''
            attr_line = self.product_tmpl_id.attribute_line_ids.filtered(
                lambda l: l.attribute_id == self.attribute_id
            )
            if not attr_line:
                return ''
            parts = []
            for ptav in attr_line.product_template_value_ids:
                val_name = ptav.product_attribute_value_id.name
                price = ptav.price_extra
                if price:
                    parts.append(f"{val_name} (+{price:.2f} €)")
                else:
                    parts.append(val_name)
            return ', '.join(parts)
        elif self.usage_type == 'attribute_value_change':
            if self.attribute_value_id:
                price = self.attribute_value_id.price_extra
                if price:
                    return f"+{price:.2f} €"
            return ''
        elif self.usage_type == 'product_extra':
            if self.extra_product_id:
                return f"{self.extra_product_id.lst_price:.2f} €"
            return ''
        elif self.usage_type == 'other_product':
            if self.extra_product_id and current_product:
                diff = self.extra_product_id.lst_price - current_product.lst_price
                if diff >= 0:
                    return f"+{diff:.2f} €"
                else:
                    return f"{diff:.2f} €"
            elif self.extra_product_id:
                return f"{self.extra_product_id.lst_price:.2f} €"
            return ''
        return ''


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    extra_product_config_ids = fields.One2many(
        'sale.extra.product.config',
        'product_tmpl_id',
        copy=True,
        string="Productos Extra",
    )


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def roc_create_extra_line_from_ptavs(self, product_template_id, ptav_ids, quantity, sequence):
        """Called by JS after user selects attribute values in the product configurator dialog."""
        self.ensure_one()
        selected = set(ptav_ids)
        candidates = self.env['product.product'].search([
            ('product_tmpl_id', '=', product_template_id)
        ])
        product = candidates.filtered(
            lambda p: set(p.product_template_attribute_value_ids.ids) == selected
        )[:1]
        if not product:
            product = candidates[:1]
        if product:
            self.env['sale.order.line'].create({
                'order_id': self.id,
                'product_id': product.id,
                'name': product.get_product_multiline_description_sale(),
                'product_uom_qty': quantity,
                'product_uom': product.uom_id.id,
                'price_unit': product.lst_price,
                'sequence': sequence,
            })
        return True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id.product_tmpl_id.extra_product_config_ids',
                 'product_id.product_tmpl_id.extra_product_config_ids.usage_type')
    def _compute_has_extra_products(self):
        for line in self:
            configs = line.product_id.product_tmpl_id.extra_product_config_ids.filtered(
                lambda x: x.usage_type in ('attribute_change', 'attribute_value_change', 'product_extra', 'other_product')
            )
            line.has_extra_products = bool(configs)

    has_extra_products = fields.Boolean(
        compute='_compute_has_extra_products',
        string="Tiene Extras",
    )

    def open_extra_product_selector(self):
        self.ensure_one()
        wiz = self.env['sale.extra.product.selector'].create({
            'sale_line_id': self.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Agregar Extra',
            'res_model': 'sale.extra.product.selector',
            'res_id': wiz.id,
            'view_mode': 'form',
            'views': [(self.env.ref('roc_custom.view_sale_extra_product_selector_form').id, 'form')],
            'target': 'new',
        }
