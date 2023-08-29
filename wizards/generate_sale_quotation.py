from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta



class GenerateSaleQuotation(models.TransientModel):
    _name = 'generale.sale.quotation'

    @api.model
    def default_get(self, fields):
        result = super(GenerateSaleQuotation, self).default_get(fields)
        if not result.get('lead_id') and self.env.context.get('active_id'):
            result['lead_id'] = self.env.context.get('active_id')
        return result
    lead_id = fields.Many2one('crm.lead')
    sale_quotation_template_ids = fields.Many2many(comodel_name='sale.order.template')

    def action_done(self):
        so_to_create = []
        for template in self.sale_quotation_template_ids:
            vals = {
                'sale_order_template_id': template.id,
                'opportunity_id': self.lead_id.id,
                'partner_id': self.lead_id.partner_id.id,
                'campaign_id': self.lead_id.campaign_id.id,
                'medium_id': self.lead_id.medium_id.id,
                'origin': self.lead_id.name,
                'source_id': self.lead_id.source_id.id,
                'company_id': self.lead_id.company_id.id or self.env.company.id,
                'tag_ids': [(6, 0, self.lead_id.tag_ids.ids)]
            }
            so_to_create.append(vals)
        new_so = self.env['sale.order'].create(so_to_create)
        for so in new_so:
            so.onchange_sale_order_template_id()
        return False


