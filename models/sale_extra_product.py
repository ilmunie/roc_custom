from odoo import fields, models, api


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
        ('other_product', 'Otro Producto'),
    ], required=True, string="Tipo de Uso")
    extra_product_id = fields.Many2one(
        'product.product',
        string="Producto Extra",
    )


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
                'name': product.display_name,
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
                lambda x: x.usage_type in ('attribute_change', 'other_product')
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
