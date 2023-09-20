from odoo import fields, models, api
import json

class StockPicking(models.Model):
    _inherit = "stock.picking"
    _order = 'create_date desc'

    product_template_id = fields.Many2one(related='move_ids_without_package.product_template_id', string="Plantilla de producto")

    picking_type_code = fields.Selection(related="picking_type_id.code")
    see_invoice_number = fields.Boolean(copy=False)
    see_shipment_number = fields.Boolean(copy=False)
    invoice_number = fields.Char(string='Nro Factura proveedor', copy=False, tracking=True)
    shipment_number = fields.Char(string='Nro Remito proveedor', copy=False, tracking=True)

class StockMove(models.Model):
    _inherit = "stock.move"

    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id")
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', default=True)
    @api.depends('product_id', 'picking_id.state')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel']:
                line.product_updatable = False
            else:
                line.product_updatable = True
    product_custom_attribute_value_ids = fields.One2many('product.attribute.custom.value', 'stock_move_id', string="Custom Values SM", copy=True)
    product_no_variant_attribute_value_ids = fields.Many2many('product.template.attribute.value', string="Extra Values", ondelete='restrict')
    is_configurable_product = fields.Boolean('Is the product configurable?', related="product_template_id.has_configurable_attributes")
    product_template_attribute_value_ids = fields.Many2many(related='product_id.product_template_attribute_value_ids', readonly=True)

class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id")
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', default=True)
    @api.depends('product_id', 'picking_id.state')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel']:
                line.product_updatable = False
            else:
                line.product_updatable = True
    product_custom_attribute_value_ids = fields.One2many('product.attribute.custom.value', 'stock_move_line_id', string="Custom Values SML", copy=True)
    product_no_variant_attribute_value_ids = fields.Many2many('product.template.attribute.value', string="Extra Values", ondelete='restrict')
    is_configurable_product = fields.Boolean('Is the product configurable?', related="product_template_id.has_configurable_attributes")
    product_template_attribute_value_ids = fields.Many2many(related='product_id.product_template_attribute_value_ids', readonly=True)