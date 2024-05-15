from odoo import fields, models, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    def compute_purchase_order(self):
        for record in self:
            record.purchase_order_ids = [(6,0,self.env['purchase.order'].search([('origin', 'ilike', record.name)]).mapped('id'))]
    purchase_order_ids = fields.Many2many('purchase.order', compute=compute_purchase_order)
