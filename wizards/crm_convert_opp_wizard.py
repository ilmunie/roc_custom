from odoo import api, fields, models, SUPERUSER_ID, _


class Lead2OpportunityPartner(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner'

    @api.depends('duplicated_lead_ids')
    def _compute_name(self):
        for convert in self:
            if not convert.name:
                convert.name = 'convert'

    installation = fields.Boolean(related='lead_id.installation', readonly=False)
    tag_ids = fields.Many2many(related='lead_id.tag_ids', readonly=False)
    intrest_tag_ids = fields.Many2many(related='lead_id.intrest_tag_ids', readonly=False)
    source_id = fields.Many2one(related='lead_id.source_id', readonly=False)
    referred = fields.Char(related='lead_id.referred', readonly=False)
    customer_concern = fields.Selection(related='lead_id.customer_concern', readonly=False)
    type_of_client = fields.Selection(related='lead_id.type_of_client', readonly=False)

def action_apply(self):
    return super(Lead2OpportunityPartner, self).action_apply()





            