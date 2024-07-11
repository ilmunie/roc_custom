from odoo import fields, models, api
import pytz

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



    def _apply_invoice_payments(self):
        payment_moves = self.payment_ids.sudo().with_company(self.company_id)._create_payment_moves()
        self.account_move.js_assign_outstanding_line(payment_moves.mapped('line_ids').filtered(lambda x: x.account_id.user_type_id.name in ('Receivable','Por cobrar'))[-1].id)
                #payment_receivables = payment_moves.mapped('line_ids').filtered(lambda line: line.account_id == receivable_account and line.partner_id)
                #(invoice_receivables | payment_receivables).sorted(key=lambda l: l.amount_currency).sudo().with_company(self.company_id).reconcile()