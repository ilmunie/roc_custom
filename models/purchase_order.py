from odoo import fields, models, api
import json

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    _order = 'create_date desc'

    @api.depends('state', 'order_line', 'order_line.qty_received', 'order_line.product_qty')
    def compute_reception_status(self):
        for record in self:
            if record.state in ('purchase', 'done'):
                partial = False
                full = True
                for line in record.order_line:
                    if not partial and line.qty_received > 0:
                        partial = True
                    if full and line.qty_received < line.product_qty:
                        full = False
                if full:
                    record.reception_status = 'full_reception'
                elif partial:
                    record.reception_status = 'partial_reception'
                else:
                    record.reception_status = 'waiting_reception'
            else:
                record.reception_status = 'no_confirmed'

    reception_status = fields.Selection(string='Estado de recepción', selection=[('no_confirmed', 'No confirmada'), ('waiting_reception', 'Esperando recepción'), ('partial_reception', 'Recepción parcial'), ('full_reception','Completamente recibida')],store=True, compute=compute_reception_status)
