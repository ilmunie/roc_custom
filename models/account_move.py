from odoo import fields, models, _, api
import json

class PaymentWay(models.Model):
    _name = 'payment.way'

    name = fields.Char(string='Nombre', required=True)
    invoice_payment_instructions = fields.Text(string='Instrucciones factura', required=True)

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    default_payable_account_id = fields.Many2one('account.account', string="Cuenta a cobrar", domain=[('internal_type','=','receivable'),('deprecated','=',False)])
    invoice_payment_label = fields.Char(string="Etiqueta pago (factura)")


class AccountMove(models.Model):
    _inherit = 'account.move'

    payment_journal_instruction_ids = fields.Many2many(comodel_name='payment.way', string="Medios de pago")
    @api.depends('amount_residual')
    def compute_invoice_date(self):
        for record in self:
            res = False if record.trigger_compute_invoice_date else True
            if record.state == 'posted':
                record._compute_invoice_date()
            record.trigger_compute_invoice_date = res

    trigger_compute_invoice_date = fields.Boolean(compute='compute_invoice_date', store=True)
    @api.depends('partner_id')
    def get_domain_shipping(self):
        for record in self:
            domain = [('id','=',0)]
            if record.partner_id:
                domain = ['|',('id', '=', record.partner_id.id), ('parent_id', '=', record.partner_id.id)]
            record.shipping_domain_id = json.dumps(domain)

    shipping_domain_id = fields.Char(compute=get_domain_shipping)
    def _compute_invoice_date(self):
        ''' Compute the dynamic payment term lines of the journal entry.'''
        self.ensure_one()
        self = self.with_company(self.company_id)
        in_draft_mode = self != self._origin
        today = fields.Date.context_today(self)
        self = self.with_company(self.journal_id.company_id)

        def _get_payment_terms_computation_date(self):
            ''' Get the date from invoice that will be used to compute the payment terms.
            :param self:    The current account.move record.
            :return:        A datetime.date object.
            '''
            if self.invoice_payment_term_id:
                return self.invoice_date or today
            else:
                return self.invoice_date_due or self.invoice_date or today

        def _get_payment_terms_account(self, payment_terms_lines):
            ''' Get the account from invoice that will be set as receivable / payable account.
            :param self:                    The current account.move record.
            :param payment_terms_lines:     The current payment terms lines.
            :return:                        An account.account record.
            '''
            if payment_terms_lines:
                # Retrieve account from previous payment terms lines in order to allow the user to set a custom one.
                return payment_terms_lines[0].account_id
            elif self.partner_id:
                # Retrieve account from partner.
                if self.is_sale_document(include_receipts=True):
                    return self.partner_id.property_account_receivable_id
                else:
                    return self.partner_id.property_account_payable_id
            else:
                # Search new account.
                domain = [
                    ('company_id', '=', self.company_id.id),
                    ('internal_type', '=', 'receivable' if self.move_type in ('out_invoice', 'out_refund', 'out_receipt') else 'payable'),
                    ('deprecated', '=', False),
                ]
                return self.env['account.account'].search(domain, limit=1)

        def _compute_payment_terms(self, date, total_balance, total_amount_currency):
            ''' Compute the payment terms.
            :param self:                    The current account.move record.
            :param date:                    The date computed by '_get_payment_terms_computation_date'.
            :param total_balance:           The invoice's total in company's currency.
            :param total_amount_currency:   The invoice's total in invoice's currency.
            :return:                        A list <to_pay_company_currency, to_pay_invoice_currency, due_date>.
            '''
            if self.invoice_payment_term_id:
                to_compute = self.invoice_payment_term_id.compute(total_balance, date_ref=date, currency=self.company_id.currency_id)
                if self.currency_id == self.company_id.currency_id:
                    # Single-currency.
                    return [(b[0], b[1], b[1]) for b in to_compute]
                else:
                    # Multi-currencies.
                    to_compute_currency = self.invoice_payment_term_id.compute(total_amount_currency, date_ref=date, currency=self.currency_id)
                    return [(b[0], b[1], ac[1]) for b, ac in zip(to_compute, to_compute_currency)]
            else:
                return [(fields.Date.to_string(date), total_balance, total_amount_currency)]

        def _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute):
            ''' Process the result of the '_compute_payment_terms' method and creates/updates corresponding invoice lines.
            :param self:                    The current account.move record.
            :param existing_terms_lines:    The current payment terms lines.
            :param account:                 The account.account record returned by '_get_payment_terms_account'.
            :param to_compute:              The list returned by '_compute_payment_terms'.
            '''
            # As we try to update existing lines, sort them by due date.
            existing_terms_lines = existing_terms_lines.sorted(lambda line: line.date_maturity or today)
            existing_terms_lines_index = 0

            # Recompute amls: update existing line or create new one for each payment term.
            new_terms_lines = self.env['account.move.line']
            for date_maturity, balance, amount_currency in to_compute:
                currency = self.journal_id.company_id.currency_id
                if currency and currency.is_zero(balance) and len(to_compute) > 1:
                    continue

                if existing_terms_lines_index < len(existing_terms_lines):
                    # Update existing line.
                    candidate = existing_terms_lines[existing_terms_lines_index]
                    existing_terms_lines_index += 1
                    candidate.update({
                        'date_maturity': date_maturity,
                        'amount_currency': -amount_currency,
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                    })
                else:
                    # Create new line.
                    create_method = in_draft_mode and self.env['account.move.line'].new or self.env['account.move.line'].create
                    candidate = create_method({
                        'name': self.payment_reference or '',
                        'debit': balance < 0.0 and -balance or 0.0,
                        'credit': balance > 0.0 and balance or 0.0,
                        'quantity': 1.0,
                        'amount_currency': -amount_currency,
                        'date_maturity': date_maturity,
                        'move_id': self.id,
                        'currency_id': self.currency_id.id,
                        'account_id': account.id,
                        'partner_id': self.commercial_partner_id.id,
                        'exclude_from_invoice_tab': True,
                    })
                new_terms_lines += candidate
                if in_draft_mode:
                    candidate.update(candidate._get_fields_onchange_balance(force_computation=True))
            return new_terms_lines

        existing_terms_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        others_lines = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type not in ('receivable', 'payable'))
        company_currency_id = (self.company_id or self.env.company).currency_id
        total_balance = sum(others_lines.mapped(lambda l: company_currency_id.round(l.balance)))
        total_amount_currency = sum(others_lines.mapped('amount_currency'))
        computation_date = _get_payment_terms_computation_date(self)
        account = _get_payment_terms_account(self, existing_terms_lines)
        to_compute = _compute_payment_terms(self, computation_date, total_balance, total_amount_currency)
        new_terms_lines = _compute_diff_payment_terms_lines(self, existing_terms_lines, account, to_compute)
        if new_terms_lines.filtered(lambda x: x.amount_residual > 0):
            self.invoice_date_due = new_terms_lines.filtered(lambda x: x.amount_residual > 0)[0].date_maturity



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

    def _get_reconciled_vals(self, partial, amount, counterpart_line):
        res = super(AccountMove, self)._get_reconciled_vals(partial, amount, counterpart_line)
        res['invoice_payment_label'] = counterpart_line.journal_id.invoice_payment_label or ''
        return res