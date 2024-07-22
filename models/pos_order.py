from odoo import fields, models, api, _
import pytz
from odoo.exceptions import UserError, ValidationError


class PosSession(models.Model):
    _inherit = 'pos.session'

    def custom_close_session(self):
        self.ensure_one()
        """
        1. Hace factura simplificada de pedidos con valor > 0 con fecha correspondiente
        2. Hace asientos contables de Registros de caja
        3. Cambia estado de sesion
        """
        #1. Facturas simplificadas
        min_close_date = self.env.context.get('min_close_date', False)
        for order in self.order_ids.filtered(lambda x: x.amount_total and x.is_l10n_es_simplified_invoice and x.state not in ('draft', 'cancel', 'invoiced')):
            date = order.date_order.date()
            if date < min_close_date:
                order.with_context(billing_date=min_close_date)._generate_pos_order_simplified_invoice()
            else:
                order.with_context(billing_date=False)._generate_pos_order_simplified_invoice()
        #2. Asientos contables registros de caja: retiros - devoluciones clientes
        cash_movement_lines = self.cash_register_id.move_line_ids.filtered(lambda x: x.account_id.code == '572001')
        for cash_move_line in cash_movement_lines:
            if 'RET' in (cash_move_line.name or '').upper():
                #RETIRO DAVID
                cash_move_line.account_id = self.env.ref('l10n_es.1_pgc_pyme_551').id
            elif 'DEV' in (cash_move_line.name or '').upper():
                False
                #DEVOLUCION A CLIENTE
                #cash_move_line.account_id = False
            elif 'ING' in (cash_move_line.name or '').upper():
                #INGRESO A CAJA
                cash_move_line.account_id = False
            elif 'OPENING' in (cash_move_line.name or '').upper():
                # ASIENTO APERTURA
                cash_move_line.account_id = self.env.ref('l10n_es.1_pgc_pyme_551').id
            elif 'DIF' in (cash_move_line.name or '').upper():
                # ASIENTO APERTURA
                False
                #cash_move_line.account_id = self.env.ref('l10n_es.1_pgc_pyme_551').id
            else:
                return UserError('Etiqueta de movimiento de efectivo no estandarizada. Comuniquese con el administrador del sistema')
        #2.2. Valido asientos
        self.cash_register_id.button_post()
        #3. Cambia estado de sesion
        self.state = 'closed'
        return False

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    pos_order_ids = fields.One2many('pos.order', 'opportunity_id')
    def pos_count(self):
        for record in self:
            record.pos_order_count = len(record.pos_order_ids.mapped('id'))
    pos_order_count = fields.Integer(compute=pos_count)

    def action_view_pos_order(self):
        self.ensure_one()
        linked_orders = self.pos_order_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedidos Punto de venta' if len(linked_orders) > 1 else linked_orders[0].display_name,
            'res_id': linked_orders[0].id,
            'res_model': 'pos.order',
            'view_mode': 'tree,form' if len(linked_orders) > 1 else 'form',
            'domain': [('id', 'in', linked_orders.ids)],
        }
class PosOrder(models.Model):
    _inherit = 'pos.order'

    def action_view_po(self):
        self.ensure_one()
        linked_orders = self.purchase_order_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedidos de compra generados' if self.purchase_order_count > 1 else self.purchase_order_ids[0].display_name,
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_ids[0].id,
            'view_mode': 'tree,form' if self.purchase_order_count > 1 else 'form',
            'domain': [('id', 'in', linked_orders.ids)],
        }
    def compute_purchase_order(self):
        for record in self:
            pos = self.env['purchase.order'].search([('origin', 'ilike', record.name)]).mapped('id')
            record.purchase_order_ids = [(6, 0, pos)]
            record.purchase_order_count = len(pos)
    purchase_order_ids = fields.Many2many('purchase.order', compute=compute_purchase_order)
    purchase_order_count = fields.Integer(compute=compute_purchase_order)
    opportunity_id = fields.Many2one('crm.lead', string="Oportunidad")

    @api.depends('state')
    def create_opportunity(self):
        for record in self:
            if record.sale_order_count > 0:
                leads = record.lines.mapped('sale_order_origin_id.opportunity_id')
                record.opportunity_id = leads[0].id if leads else False
            if record.sale_order_count == 0 and record.state in ('paid', 'done', 'invoiced') and not record.opportunity_id:
                user = False
                if record.employee_id.user_id:
                    user = record.employee_id.user_id.id
                else:
                    users = self.env['res.users'].search([('login','=',record.employee_id.work_email)])
                    if users:
                        user = users[0].id
                medium = False
                mediums = self.env['utm.medium'].search([('name', '=', 'TIENDA')])
                if mediums:
                    medium = mediums[0].id
                source = False
                sources = self.env['utm.source'].search([('name', '=', 'tienda')])
                if sources:
                    source = sources[0].id
                partner = False
                if record.partner_id:
                    partner = record.partner_id.id
                else:
                    generic_partnerts = self.env['res.partner'].search([('name','=','CLIENTE GENERICO')])
                    if generic_partnerts:
                        partner = generic_partnerts[0].id

                opportunity_vals = {
                    'name': record.name,
                    'type': 'opportunity',
                    'partner_id': partner,
                    'stage_id': self.env.ref('crm.stage_lead4').id,
                    'expected_revenue': record.amount_total - record.amount_tax,
                    'user_id': user,
                    'medium_id': medium,
                    'source_id': source,
                    'team_id': self.env.ref('sales_team.pos_sales_team').id,
                }
                opp = self.env['crm.lead'].create(opportunity_vals)
                record.opportunity_id = opp.id
            record.trigger_create_opportunity = False if record.trigger_create_opportunity else True
    trigger_create_opportunity = fields.Boolean(compute=create_opportunity, store=True)


    def _create_invoice(self, move_vals):
        res = super(PosOrder, self)._create_invoice(move_vals)
        for rec in res:
            for note_line in rec.invoice_line_ids.filtered(lambda x: not x.product_id):
                rec.invoice_line_ids = [(2, note_line.id)]
            if rec.journal_id.default_payable_account_id.id:
                rec_line = rec.line_ids.filtered(lambda x: x.account_id.user_type_id.name in ('Receivable','Por cobrar'))
                rec_line.account_id = rec.journal_id.default_payable_account_id.id
        return res

    def _prepare_invoice_vals(self):
        res = super(PosOrder, self)._prepare_invoice_vals()
        billing_date = self.env.context.get('billing_date', False)
        if billing_date:
            res['invoice_date'] = billing_date
        return res

    def _generate_pos_order_simplified_invoice(self):
        moves = self.env['account.move']
        for order in self:
            # Force company for all SUPERUSER_ID action
            if order.account_move:
                moves += order.account_move
                continue
            move_vals = order._prepare_invoice_vals()
            journal = self.env['account.journal'].search([('name','=','Facturas simplificadas')])
            if not journal:
                UserWarning('Cree un diario de ventas Facturas simplificadas')
            move_vals['journal_id'] = journal[0].id
            if not order.partner_id or not order.partner_id.vat:
                if order.opportunity_id and order.opportunity_id.partner_id and order.opportunity_id.partner_id.vat:
                    move_vals['partner_id'] = order.opportunity_id.partner_id
                else:
                    generic_partnerts = self.env['res.partner'].search([('name','=','CLIENTE GENERICO')])
                    if generic_partnerts:
                        move_vals['partner_id'] = generic_partnerts[0].id
            new_move = order._create_invoice(move_vals)
            order.write({'account_move': new_move.id, 'state': 'invoiced'})
            new_move.sudo().with_company(order.company_id)._post()
            moves += new_move
            order._apply_invoice_payments()

        if not moves:
            return {}

        return {
            'name': _('Customer Invoice'),
            'view_mode': 'form',
            'view_id': self.env.ref('account.view_move_form').id,
            'res_model': 'account.move',
            'context': "{'move_type':'out_invoice'}",
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'res_id': moves and moves.ids[0] or False,
        }
        return False

    def _generate_pos_order_invoice(self):
        res = False
        for order in self:
            if order.is_l10n_es_simplified_invoice:
                res = self._generate_pos_order_simplified_invoice()
            else:
                res = super(order, PosOrder)._generate_pos_order_invoice()
        return res


    def _apply_invoice_payments(self):
        payment_moves = self.payment_ids.sudo().with_company(self.company_id)._create_payment_moves()
        self.account_move.js_assign_outstanding_line(payment_moves.mapped('line_ids').filtered(lambda x: x.account_id.user_type_id.name in ('Receivable','Por cobrar'))[-1].id)
                #payment_receivables = payment_moves.mapped('line_ids').filtered(lambda line: line.account_id == receivable_account and line.partner_id)
                #(invoice_receivables | payment_receivables).sorted(key=lambda l: l.amount_currency).sudo().with_company(self.company_id).reconcile()