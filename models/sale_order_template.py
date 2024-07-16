from odoo import fields, models, api
from odoo.exceptions import UserError


class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    technical_job_template = fields.Boolean(string="Disponible trabajo tenico")


class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    technical_job_duration = fields.Boolean(string="Cant. hs T.T.")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    payment_journal_id = fields.Many2one('account.journal', domain=[('type', 'in', ('bank', 'cash'))], string="Metodo Pago")

    def bill_and_pay(self):
        self.ensure_one()
        if not self.payment_journal_id:
            raise UserError('Debe seleccionar un Metodo de pago')
        if self.state in ('draft', 'sent'):
            self.action_confirm()
        invoice = self._create_invoices()
        invoice.action_post()
        wiz = self.with_context(active_model='account.move', active_ids=invoice.mapped('id')).env['account.payment.register'].create(
            {'journal_id': self.payment_journal_id.id})
        wiz.action_create_payments()
        return False




    @api.onchange('sale_order_template_id')
    def onchange_sale_order_template_id(self):
        res = super(SaleOrder, self).onchange_sale_order_template_id()
        if self.sale_order_template_id.technical_job_template and any(line.technical_job_duration for line in self.sale_order_template_id.sale_order_template_line_ids):
            time_prod = self.sale_order_template_id.sale_order_template_line_ids.filtered(lambda x: x.technical_job_duration).mapped('product_id.id')
            lines_to_update = self.order_line.filtered(lambda x: x.product_id.id in time_prod)
            if self.opportunity_id and self.opportunity_id.total_job_minutes:
                lines_to_update.product_uom_qty = self.opportunity_id.total_job_minutes/60
        return res