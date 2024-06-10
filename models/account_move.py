from odoo import fields, models, _, api
import json
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_is_zero
class PaymentWay(models.Model):
    _name = 'payment.way'

    name = fields.Char(string='Nombre', required=True)
    invoice_payment_instructions = fields.Text(string='Instrucciones factura', required=True)


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    def _create_payment_moves(self):
        result = self.env['account.move']
        for payment in self:
            order = payment.pos_order_id
            payment_method = payment.payment_method_id
            if payment_method.type == 'pay_later' or float_is_zero(payment.amount,
                                                                   precision_rounding=order.currency_id.rounding):
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(payment.partner_id)
            pos_session = order.session_id
            journal = pos_session.config_id.journal_id
            payment_move = self.env['account.move'].with_context(default_journal_id=journal.id).create({
                'journal_id': journal.id,
                'date': fields.Date.context_today(payment),
                'ref': _('Invoice payment for %s (%s) using %s') % (
                order.name, order.account_move.name, payment_method.name),
                'pos_payment_ids': payment.ids,
            })
            result |= payment_move
            payment.write({'account_move_id': payment_move.id})
            amounts = pos_session._update_amounts({'amount': 0, 'amount_converted': 0}, {'amount': payment.amount},
                                                  payment.payment_date)
            credit_line_vals = pos_session._credit_amounts({
                'account_id': journal.default_payable_account_id.id,
                'partner_id': accounting_partner.id,
                'move_id': payment_move.id,
            }, amounts['amount'], amounts['amount_converted'])
            debit_line_vals = pos_session._debit_amounts({
                'account_id': payment.payment_method_id.receivable_account_id.id or pos_session.company_id.account_default_pos_receivable_account_id.id,
                'move_id': payment_move.id,
            }, amounts['amount'], amounts['amount_converted'])
            self.env['account.move.line'].with_context(check_move_validity=False).create(
                [credit_line_vals, debit_line_vals])
            payment_move._post()
        return result
class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

#    @api.model_create_multi
#    def create(self, vals_list):
#        #import pdb;pdb.set_trace()
#        return super(AccountMoveLine, self).create(vals_list)
#    def _check_reconciliation(self):
#        return True



    peyga_es_report_status = fields.Char(string='PEYGA ES Report Status', compute='_compute_peyga_es_report_status', store=True)
    peyga_es_report_account_prefix = fields.Char(string='PEYGA ES Report Account Prefix', compute='_compute_peyga_es_report_status', store=True)
    account_type = fields.Many2one(string="Tipo de cuenta", related="account_id.user_type_id", store=True)
    @api.depends('account_id','account_id.code')
    def _compute_peyga_es_report_status(self):
        for record in self:
            inicio_cuenta_3 = record.account_id.code[:3] if record.account_id and record.account_id.code else "fail"
            inicio_cuenta_4 = record.account_id.code[:4] if record.account_id and record.account_id.code else "fail"
            seccion_padre = ''
            seccion_especifica = ''
            table = {
                "700": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "701": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "702": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "703": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "704": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "705": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "706": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "708": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "709": ("A) RESULTADO DE EXPLOTACIÓN", "1. Importe neto de la cifra de negocios"),
                "6930": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "2. Variación de existencias de productos terminados y en curso de fabricación",
                ),
                "71": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "2. Variación de existencias de productos terminados y en curso de fabricación",
                ),
                "7930": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "2. Variación de existencias de productos terminados y en curso de fabricación",
                ),
                "73": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "3. Trabajos realizados por la empresa para su activo.",
                ),
                "600": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "601": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "602": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "606": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "607": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "608": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "609": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "61": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "6931": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "6932": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "6933": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "7931": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "7932": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "7933": ("A) RESULTADO DE EXPLOTACIÓN", "4. Aprovisionamientos"),
                "740": ("A) RESULTADO DE EXPLOTACIÓN", "5. Otros ingresos de explotación"),
                "747": ("A) RESULTADO DE EXPLOTACIÓN", "5. Otros ingresos de explotación"),
                "75": ("A) RESULTADO DE EXPLOTACIÓN", "5. Otros ingresos de explotación"),
                "64": ("A) RESULTADO DE EXPLOTACIÓN", "6. Gastos de personal"),
                "62": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "631": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "634": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "636": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "639": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "65": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "694": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "695": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "794": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "7954": ("A) RESULTADO DE EXPLOTACIÓN", "7. Otros gastos de explotación"),
                "68": ("A) RESULTADO DE EXPLOTACIÓN", "8. Amortización del inmovilizado"),
                "746 y no 7461": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "9. Imputación de subvenciones de inmovilizado no financiero y otras",
                ),
                "7951": ("A) RESULTADO DE EXPLOTACIÓN", "10. Excesos de provisiones"),
                "7952": ("A) RESULTADO DE EXPLOTACIÓN", "10. Excesos de provisiones"),
                "7955": ("A) RESULTADO DE EXPLOTACIÓN", "10. Excesos de provisiones"),
                "670": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "671": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "672": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "690": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "691": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "770": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "771": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "772": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "790": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "791": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "792": (
                    "A) RESULTADO DE EXPLOTACIÓN",
                    "11. Deterioro y resultado por enajenaciones del inmovilizado",
                ),
                "678": ("A) RESULTADO DE EXPLOTACIÓN", "12. Otros resultados"),
                "778": ("A) RESULTADO DE EXPLOTACIÓN", "12. Otros resultados"),
                "7461": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "13. Ingresos financieros a) Imputación de subvenciones, donaciones y legados de carácter financiero",
                ),
                "760": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "13.Ingresos financieros b) Otros ingresos financieros",
                ),
                "761": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "13.Ingresos financieros b) Otros ingresos financieros",
                ),
                "762": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "13.Ingresos financieros b) Otros ingresos financieros",
                ),
                "769": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "13.Ingresos financieros b) Otros ingresos financieros",
                ),
                "660": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "14. Gastos financieros",
                ),
                "661": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "14. Gastos financieros",
                ),
                "662": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "14. Gastos financieros",
                ),
                "665": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "14. Gastos financieros",
                ),
                "669": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "14. Gastos financieros",
                ),
                "663": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "15. Variación de valor razonable en instrumentos financieros",
                ),
                "763": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "15. Variación de valor razonable en instrumentos financieros",
                ),
                "668": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "16. Diferencias de cambio",
                ),
                "768": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "16. Diferencias de cambio",
                ),
                "666": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "667": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "673": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "675": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "696": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "697": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "698": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "699": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "766": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "773": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "775": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "796": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "797": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "798": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "799": (
                    "B) RESULTADO FINANCIERO (13 + 14 + 15 + 16 + 17)",
                    "17. Deterioro y resultado por enajenaciones de instrumentos financieros.",
                ),
                "6300": ("D) RESULTADO DEL EJERCICIO (C + 18)", "18. Impuestos sobre beneficios."),
                "6301": ("D) RESULTADO DEL EJERCICIO (C + 18)", "18. Impuestos sobre beneficios."),
                "633": ("D) RESULTADO DEL EJERCICIO (C + 18)", "18. Impuestos sobre beneficios."),
                "638": ("D) RESULTADO DEL EJERCICIO (C + 18)", "18. Impuestos sobre beneficios."),
            }
            prefix = ''
            if inicio_cuenta_3 in table:
                seccion_padre, seccion_especifica = table[inicio_cuenta_3]
                prefix = inicio_cuenta_3
            elif inicio_cuenta_4 in table:
                seccion_padre, seccion_especifica = table[inicio_cuenta_4]
                prefix = inicio_cuenta_4
            else:
                record.peyga_es_report_status = 'No considerado'
                prefix = inicio_cuenta_4
                continue
            record.peyga_es_report_status = f"{seccion_padre} - {seccion_especifica}"
            record.peyga_es_report_account_prefix = prefix
    def open_action_change_aml_tax_wizard(self):
        context = {'move_line_ids': self._context.get('active_ids', [])}
        open_wizard = {
            'type': 'ir.actions.act_window',
            'res_model': 'change.aml.tax.wizard',
            'view_mode': 'form',
            'context': context,
            'views': [(False, 'form')],
            'target': 'new',
        }
        return open_wizard

class AccountJournal(models.Model):
    _inherit = 'account.journal'

    default_payable_account_id = fields.Many2one('account.account', string="Cuenta a cobrar", domain=[('internal_type','=','receivable'),('deprecated','=',False)])
    invoice_payment_label = fields.Char(string="Etiqueta pago (factura)")

class TaxInvoiceReportLine(models.Model):
    _name = 'tax.invoice.report.line'

    tax_group_name = fields.Char(string="Referencia impuesto")
    amount_base = fields.Float(string="Base Imponible")
    tax_amount = fields.Float(string="Monto impuesto")



class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.depends('state')
    def compute_tax_invoice_report_line(self):
        for record in self:
            res = []
            if record.state == 'posted':
                json_data = record.tax_totals_json
                if json_data and json_data != 'false':
                    import json
                    json_data = json.loads(json_data)
                    if json_data:
                        tax_data = json_data.get('groups_by_subtotal', False)
                        if tax_data:
                            tax_lines_data = tax_data.get('Importe libre de impuestos', False)
                            if tax_lines_data:
                                for line in tax_lines_data:
                                    res.append((0, 0, {
                                                'tax_group_name': line['tax_group_name'],
                                                'amount_base': line['tax_group_base_amount'],
                                                'tax_amount': line['tax_group_amount']}))
            record.tax_invoice_report_line_ids = [(5,)] if not res else res

    tax_invoice_report_line_ids = fields.Many2many('tax.invoice.report.line', compute=compute_tax_invoice_report_line, store=True, string="Resumen de impuestos")


    def check_for_generic_account_config(self):
        active_records = self.browse(self.env.context.get('active_ids',[]))
        moves_with_wrong_accounting = []
        for move in active_records:
            if move.move_type in ('out_invoice'):
                debit_generic_line = move.line_ids.filtered(lambda x: x.debit > 0 and x.account_id.id != x.move_id.journal_id.default_payable_account_id.id and x.account_id.code != "477000000")
                if debit_generic_line:
                    moves_with_wrong_accounting.append(move.id)
                    continue
                credit_generic_line = move.line_ids.filtered(lambda x: x.credit > 0 and x.account_id.code == '700000000')
                if credit_generic_line:
                    moves_with_wrong_accounting.append(move.id)
                    continue
            elif move.move_type in ('in_invoice', 'in_refund'):
                debit_generic_line = move.line_ids.filtered(lambda x: x.debit > 0 and x.account_id.code == "600000000")
                if debit_generic_line:
                    moves_with_wrong_accounting.append(move.id)
                    continue
                credit_generic_line = move.line_ids.filtered(lambda x: x.credit > 0 and x.account_id.code == '410000000')
                if credit_generic_line:
                    moves_with_wrong_accounting.append(move.id)
                    continue
        return {
            'name': _('Asignación genérica de cuentas contables'),
            'res_model': 'account.move',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', moves_with_wrong_accounting)],
            'views': [(self.env.ref('account.view_out_invoice_tree').id, 'tree'),(self.env.ref('account.view_move_form').id,'form')] if move.move_type in ('out_invoice') else [(self.env.ref('account.view_in_invoice_bill_tree').id, 'tree'),(self.env.ref('account.view_move_form').id,'form')],
        }


    def regenerate_account_moves(self):
        for record in self:
            if record.move_type not in ('out_invoice','in_invoice'):
                continue
            move_type = record.move_type
            post = False
            payments = []
            if record.invoice_payments_widget:
                dict = json.loads(record.invoice_payments_widget)
                if dict and 'content' in dict and dict['content']:
                    for payment in dict['content']:
                        payments.append(payment['account_payment_id'])
            for payment in payments:
                payment_rec = self.env['account.payment'].browse(payment)
                payment_rec.action_draft()
            if record.state == 'posted':
                post = True
                record.button_draft()
            if move_type == 'in_invoice':
                #partner_generic_account = True
                partner_generic_account = record.line_ids.filtered(lambda x: x.account_id and x.account_id.code == '410000000')
                if partner_generic_account:
                    record._onchange_partner_id()
                    record._recompute_dynamic_lines()
                    for payment in payments:
                        payment_rec = self.env['account.payment'].browse(payment)
                        payment_rec.partner_id = False
                        payment_rec.partner_id = record.partner_id.id

            for line in record.invoice_line_ids.filtered(lambda x: x.product_id):
                line.account_id = line._get_computed_account()
            if post:
                record.action_post()
            for payment in payments:
                payment_rec = self.env['account.payment'].browse(payment)
                payment_rec.action_post()
                conciliable_line = payment_rec.line_ids.filtered('credit') if move_type == 'out_invoice' else payment_rec.line_ids.filtered('debit')
                record.js_assign_outstanding_line(conciliable_line.id)

    @api.constrains("ref", "partner_id")
    def _check_supplier_invoice_duplicity(self):
        for rec in self:
            if rec.ref and rec.partner_id and rec.move_type and rec.move_type in ('in_invoice', 'in_refund'):
                matching_rec = self.env['account.move'].search([('partner_id','=',rec.partner_id.id),('move_type','=', rec.move_type),('ref','=',rec.ref),('id','!=',rec.id)])
                if matching_rec:
                    raise ValidationError("Ya existe una factura/reembolso para este proveedor con la misma referencia")
    @api.depends('aux_payment_date','aux_journal_id')
    def trigger_create_pay(self):
        for record in self:
            if record.aux_payment_date and record.aux_journal_id:
                payment = self.env['account.payment'].create({
                    'date': record.aux_payment_date,
                    'payment_type': 'outbound' if record.move_type == 'in_invoice' else 'inbound',
                    'partner_type': 'supplier' if record.move_type == 'in_invoice' else 'customer',
                    'partner_id': record.partner_id.id,
                    'amount': abs(record.amount_total_signed),
                    'currency_id': self.env.user.company_id.currency_id.id,
                    'journal_id': record.aux_journal_id.id,
                    'destination_account_id': record.line_ids.filtered(lambda x: x.account_id.user_type_id.name in ('Por cobrar', 'Receivable'))[0].account_id.id,
                })
                payment.action_post()
                if record.move_type == 'in_invoice':
                    receivable_line = payment.line_ids.filtered(lambda x: x.debit > 0)
                    record.js_assign_outstanding_line(receivable_line.id)
                else:
                    payable_line = payment.line_ids.filtered(lambda x: x.credit > 0)
                    record.js_assign_outstanding_line(payable_line.id)
            record.trigger_create_payment = False if record.trigger_create_payment else False

    trigger_create_payment = fields.Boolean(compute=trigger_create_pay, store=True)
    aux_payment_date = fields.Date()
    aux_journal_id = fields.Many2one('account.journal')

    nif = fields.Char(related='partner_id.vat', store=True, string="NIF")

    @api.depends('invoice_line_ids.sale_line_ids.order_id.invoice_ids')
    def get_so(self):
        for record in self:
            #import pdb;pdb.set_trace()
            po = self.env['sale.order'].search([('invoice_ids', '!=', False),('invoice_ids', '=', record.id)])
            if po:
                record.sale_order_id = po[0].id
                if po[0].journal_id:
                    record.journal_id = po[0].journal_id.id
            else:
                record.sale_order_id = False
            record.opportunity_id = po[0].opportunity_id.id if po and po[0].opportunity_id else False

    sale_order_id = fields.Many2one('sale.order',string="Órden de venta", compute=get_so, store=True)
    opportunity_id = fields.Many2one('crm.lead', compute=get_so, store=True, string="Oportunidad")

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

    def _prepare_tax_lines_data_for_totals_from_invoice(self, tax_line_id_filter=None, tax_ids_filter=None):
        res = super(AccountMove,self)._prepare_tax_lines_data_for_totals_from_invoice(tax_line_id_filter=tax_line_id_filter,tax_ids_filter=tax_ids_filter)
        #import pdb;pdb.set_trace()
        return res

    def _get_tax_totals(self, partner, tax_lines_data, amount_total, amount_untaxed, currency):
        res = super(AccountMove,self)._get_tax_totals(partner, tax_lines_data, amount_total, amount_untaxed, currency)
        return res




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

