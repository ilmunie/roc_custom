from odoo import fields, models, api
from odoo.exceptions import UserError
import json
class SaleOrderTemplateTag(models.Model):
    _name = 'sale.order.template.tag'

    name = fields.Char()
    category = fields.Selection(selection=[('pack_type', 'Tipo pack'),('component', 'Componente'), ('door_type', 'Tipo puerta')])

class SaleOrderTemplate(models.Model):
    _inherit = 'sale.order.template'

    technical_job_template = fields.Boolean(string="Disponible trabajo tenico")
    sale_attachment_id = fields.Many2one('ir.attachment', string="Material comercial")
    sale_template_tag_ids = fields.Many2many('sale.order.template.tag', string="Etiquetas plantilla")

class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    technical_job_duration = fields.Boolean(string="Cant. hs T.T.")
    discount = fields.Float(string="Descuento")
    alternative_product_domain = fields.Char(string="Productos Alternativos")
   

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
        for order_line in self.order_line.filtered(lambda x: x.sale_template_line_id):
            order_line.discount = order_line.sale_template_line_id.discount*100
        return res
    
    def _compute_line_data_for_template_change(self, line):
        vals = super(SaleOrder, self)._compute_line_data_for_template_change(line)
        vals['sale_template_line_id'] = line.id
        return vals

    @api.depends('sale_template_tag_ids')
    def compute_tag_domain(self):
        for record in self:
            res = [('id', '!=', 0)]
            if record.sale_template_tag_ids:
                for tag in record.sale_template_tag_ids:
                    res.append(('sale_template_tag_ids.name', '=', tag.name))
            record.sale_template_domain = json.dumps(res)

    sale_template_tag_ids = fields.Many2many('sale.order.template.tag', string="Etiquetas plantilla")
    sale_template_domain = fields.Char(compute=compute_tag_domain)
    sale_template_tag_selector = fields.Selection(selection=[('pack_type', 'Tipo pack'),('component', 'Componente'), ('door_type', 'Tipo puerta')])
    
    @api.depends('sale_template_tag_selector')
    def compute_sale_template_tag_domain(self):
        for record in self:
            res = [('id', '!=', 0)]
            if record.sale_template_tag_selector:
                res = [('category', '=', record.sale_template_tag_selector)]
            record.sale_template_tag_domain = json.dumps(res) 

    sale_template_tag_domain = fields.Char(compute="compute_sale_template_tag_domain")
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    
    sale_template_line_id = fields.Many2one('sale.order.template.line')


    @api.depends('sale_template_line_id')
    def get_alternative_prod_domain(self):
        for record in self:
            res = []
            if record.sale_template_line_id:
                if record.sale_template_line_id.alternative_product_domain:
                    res.extend(json.loads(record.sale_template_line_id.alternative_product_domain))
            record.alternative_product_domain = json.dumps(res)

    alternative_product_domain = fields.Char(compute=get_alternative_prod_domain, store=True)

    def open_alternative_products(self):
        context = {
                #'required_attr_name': self.raw_material_production_id.product_id.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in self.bom_line_id.force_attributes_value_ids.mapped('id')).mapped('name') or [],
                #'required_attr_ids': self.raw_material_production_id.product_id.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in self.bom_line_id.force_attributes_value_ids.mapped('id')).mapped('id') or [],
                'sale_template_id': self.order_id.sale_order_template_id.id,
                'domain': self.alternative_product_domain,
                'sale_line_id': self.id,
                'qty': self.product_uom_qty,
                'location': self.order_id.warehouse_id.lot_stock_id.id,
                #'attr_values': self.raw_material_production_id.product_id.product_template_variant_value_ids.mapped('id'),
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.alternative.product.assistant',
            'context': context,
            'view_mode': 'form',
            'views': [(self.env.ref('roc_custom.sale_alternative_product_assistant_wizard_view').id, 'form')],
            'target': 'new',
        }