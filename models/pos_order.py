from odoo import fields, models, api

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
            'name': 'Pedidos Punto de venta',
            'res_model': 'pos.order',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', linked_orders.ids)],
        }
class PosOrder(models.Model):
    _inherit = 'pos.order'

    def compute_purchase_order(self):
        for record in self:
            record.purchase_order_ids = [(6,0,self.env['purchase.order'].search([('origin', 'ilike', record.name)]).mapped('id'))]
    purchase_order_ids = fields.Many2many('purchase.order', compute=compute_purchase_order)
    opportunity_id = fields.Many2one('crm.lead')

    @api.depends('state')
    def create_opportunity(self):
        for record in self:
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
            if rec.journal_id.default_payable_account_id.id:
                rec_line = rec.line_ids.filtered(lambda x: x.account_id.user_type_id.name in ('Receivable','Por cobrar'))
                rec_line.account_id = rec.journal_id.default_payable_account_id.id
        return res


    def _apply_invoice_payments(self):
        payment_moves = self.payment_ids.sudo().with_company(self.company_id)._create_payment_moves()
        self.account_move.js_assign_outstanding_line(payment_moves.mapped('line_ids').filtered(lambda x: x.account_id.user_type_id.name in ('Receivable','Por cobrar')).id)
                #payment_receivables = payment_moves.mapped('line_ids').filtered(lambda line: line.account_id == receivable_account and line.partner_id)
                #(invoice_receivables | payment_receivables).sorted(key=lambda l: l.amount_currency).sudo().with_company(self.company_id).reconcile()