from odoo import api, fields, models, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = "sale.advance.payment.inv"

    @api.model
    def default_get(self, fields):
        result = super(SaleAdvancePaymentInv, self).default_get(fields)
        result['amount'] = 50
        if self.env.context.get('active_id'):
            sale = self.env['sale.order'].browse(self.env.context.get('active_id'))
            if sale.invoice_ids.filtered(lambda x: x.state not in ('cancel')):
                result['advance_payment_method'] = 'delivered'
            else:
                result['advance_payment_method'] = 'percentage'
        return result