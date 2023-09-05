from odoo import fields, models, _, api

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    default_payable_account_id = fields.Many2one('account.account', string="Cuenta a cobrar", domain=[('internal_type','=','receivable'),('deprecated','=',False)])
class AccountMove(models.Model):
    _inherit = 'account.move'

    def _recompute_dynamic_lines(self, recompute_all_taxes=False, recompute_tax_base_amount=False):
        res = super(AccountMove,self)._recompute_dynamic_lines(recompute_all_taxes=recompute_all_taxes,recompute_tax_base_amount=recompute_tax_base_amount)
        for invoice in self:
            if invoice.journal_id and invoice.journal_id.default_payable_account_id:
                receivable_account_id = invoice.journal_id.default_payable_account_id.id
                for line in invoice.line_ids.filtered(lambda x: x.account_id.user_type_id.name in ('receivable','Por cobrar')):
                    line.account_id = receivable_account_id
        return res
    @api.onchange('journal_id')
    def _onchange_journal_recompute(self):
        self._recompute_dynamic_lines()
