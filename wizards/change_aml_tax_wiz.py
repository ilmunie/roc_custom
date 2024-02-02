from odoo import api, fields, models, _
import json

class ChangeAmlTaxWizard(models.TransientModel):
    _name = "change.aml.tax.wizard"

    tax_ids = fields.Many2many('account.tax')
    def action_done(self):
        move_lines = self._context.get('move_line_ids', [])
        move_lines_rec = self.env['account.move.line'].browse(move_lines)
        move_ids = move_lines_rec.filtered(lambda x: x.move_id.move_type in ('in_invoice','out_invoice','out_refund','in_refund')).mapped('move_id')
        done_moves_ids = []
        for move in move_ids:
            if move.id in done_moves_ids:
                continue
            else:
                done_moves_ids.append(move.id)
            lines_to_reconcile = []
            json_invoice_payments_widget = json.loads(move.invoice_payments_widget)
            if json_invoice_payments_widget:
                for payment in json_invoice_payments_widget['content']:
                    payment_rec = self.env['account.payment'].browse(payment['account_payment_id'])
                    if not payment_rec:
                        payment_rec = self.env['account.move'].browse(payment['move_id'])
                    if move.move_type not in ('out_invoice', 'in_refund'):
                        lines_to_reconcile.append(payment_rec.line_ids.filtered('debit'))
                    else:
                        lines_to_reconcile.append(payment_rec.line_ids.filtered('credit'))
            move.button_draft()
            for ml in move_lines_rec.filtered(lambda x: x.move_id.id == move.id):
                ml.tax_ids = [(6,0, self.tax_ids.mapped('id'))]
            move.with_context(check_move_validity=False)._recompute_dynamic_lines(recompute_all_taxes=True, recompute_tax_base_amount=True)
            move.action_post()
            for rec_line in lines_to_reconcile:
                move.js_assign_outstanding_line(rec_line.id)
        return False

