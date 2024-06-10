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