from odoo import fields, models


class MassivePosBilling(models.TransientModel):
    _name = 'massive.pos.billing'

    billing_date_type = fields.Selection(selection=[('pos_order_date', 'Fecha venta'), ('special_date', 'Fecha especial')], string="Fecha facturación")

    special_date = fields.Date(string="Fecha")
    def action_done(self):
        pos_orders = self.env['pos.order'].browse(self._context.get('active_ids', ['pos.order']))
        if self.billing_date_type == 'pos_order_date':
            pos_orders.action_pos_order_invoice()
        else:
            pos_orders.with_context(billing_date=self.special_date).action_pos_order_invoice()
        return
            
