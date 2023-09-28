from odoo import api, fields, models, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.model
    def default_get(self, fields):
        result = super(AccountPaymentRegister, self).default_get(fields)
        invoices = self.env['account.move'].browse(self.env.context.get('active_id'))
        result['communication'] = ','.join(invoices.mapped('name'))
        return result



