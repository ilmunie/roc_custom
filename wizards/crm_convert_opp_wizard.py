from odoo import api, fields, models, SUPERUSER_ID, _

class Lead2OpportunityMassConvert(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner.mass'

    @api.depends('lead_tomerge_ids')
    def _compute_duplicated_lead_ids(self):
        for convert in self:
            duplicated = self.env['crm.lead']
            for lead in convert.lead_tomerge_ids:
                duplicated_leads = self.env['crm.lead']._get_lead_duplicates_custom(
                    partner=lead.partner_id,
                    email=lead.partner_id and lead.partner_id.email or lead.email_from,
                    phone=lead.partner_id.phone if lead.partner_id else lead.phone,
                    mobile=lead.partner_id.mobile if lead.partner_id else lead.mobile,
                    include_lost=False).filtered(lambda x: x.id != lead.id)
                if len(duplicated_leads) > 1:
                    duplicated += lead
            convert.duplicated_lead_ids = duplicated.ids

class Lead2OpportunityPartner(models.TransientModel):
    _inherit = 'crm.lead2opportunity.partner'

    phone = fields.Char(related='lead_id.phone', readonly=False, force_save=1)
    mobile = fields.Char(related='lead_id.mobile', readonly=False, force_save=1)
    email_from = fields.Char(related='lead_id.email_from', readonly=False, force_save=1)
    contact_name = fields.Char(related='lead_id.contact_name', readonly=False, force_save=1)

    def refresh_contact_data(self):
        action = self.env.ref('crm.action_crm_lead2opportunity_partner').read()[0]
        action['res_id'] = self.id
        if self.team_id:
            self.lead_id.team_id = self.team_id.id
        if self.user_id:
            self.lead_id.user_id = self.user_id.id
        self._compute_action()
        return action

    @api.onchange('phone', 'mobile', 'email_from', 'contact_name')
    def onchange_contact_data(self):
        self._compute_duplicated_lead_ids()

    @api.depends('lead_id', 'partner_id')
    def _compute_duplicated_lead_ids(self):
        for convert in self:
            if not convert.lead_id:
                convert.duplicated_lead_ids = False
                continue
            convert.duplicated_lead_ids = self.env['crm.lead']._get_lead_duplicates_custom(
            convert.partner_id,
            convert.lead_id.partner_id.email if convert.lead_id.partner_id and convert.lead_id.partner_id.email else convert.email_from,
            convert.lead_id.partner_id.phone if convert.lead_id.partner_id else convert.phone,
            convert.lead_id.partner_id.mobile if convert.lead_id.partner_id else convert.mobile,
            include_lost=True).filtered(lambda x: x.id != convert.lead_id.id).ids


    @api.depends('duplicated_lead_ids')
    def compute_duplicated_lead(self):
        for convert in self:
            convert.duplicate_lead_count = len(convert.duplicated_lead_ids)

    duplicate_lead_count = fields.Integer(compute=compute_duplicated_lead)
    installation = fields.Boolean(related='lead_id.installation', readonly=False)
    tag_ids = fields.Many2many(related='lead_id.tag_ids', readonly=False)
    intrest_tag_ids = fields.Many2many(related='lead_id.intrest_tag_ids', readonly=False)
    source_id = fields.Many2one(related='lead_id.source_id', readonly=False)
    medium_id = fields.Many2one(related='lead_id.medium_id', readonly=False)
    work_type_id = fields.Many2one(related='lead_id.work_type_id', readonly=False)
    referred_professional = fields.Many2one(related='lead_id.referred_professional', readonly=False)
    safety_level = fields.Selection(related='lead_id.safety_level', readonly=False)
    type_of_client = fields.Selection(related='lead_id.type_of_client', readonly=False)


    def _action_merge(self):
           to_merge = self.duplicated_lead_ids | self.lead_id
           result_opportunity = to_merge.merge_opportunity(auto_unlink=False)
           result_opportunity.action_unarchive()
           if result_opportunity.type == "lead":
               self._convert_and_allocate(result_opportunity, [self.user_id.id], team_id=self.team_id.id)
           else:
               if not result_opportunity.user_id or self.force_assignment:
                   result_opportunity.write({
                       'user_id': self.user_id.id,
                       'team_id': self.team_id.id,
                   })
           (to_merge - result_opportunity).sudo().unlink()
           return result_opportunity
