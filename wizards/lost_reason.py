from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta



class LostReasonWizard(models.TransientModel):
    _name = 'lost.reason.wizard'

    lost_reason_id = fields.Many2one(
        'lead.lost.reason', string='Motivo de la pérdida', index=True, required = True)
    observations = fields.Text(string='Aclaraciones')

    def action_done(self):
        lead_to_update_ids = self._context.get('active_ids', ['crm.lead'])
        for lead_to_update_id in lead_to_update_ids:
            lead = self.env['crm.lead'].browse(lead_to_update_id)
            lead.write({'lost_reason_id': self.lost_reason_id.id, 'lost_observations': self.observations})
            lead.action_set_lost()
            
