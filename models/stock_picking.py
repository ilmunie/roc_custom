from odoo import fields, models, api
import json

class StockPicking(models.Model):
    _inherit = "stock.picking"
    _order = 'create_date desc'


    picking_type_code = fields.Selection(related="picking_type_id.code")
    see_invoice_number = fields.Boolean(copy=False)
    see_shipment_number = fields.Boolean(copy=False)
    invoice_number = fields.Char(string='Nro Factura proveedor', copy=False)
    shipment_number = fields.Char(string='Nro Remito proveedor', copy=False)

