from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta

class ModifyTagsMassive(models.TransientModel):
    _name = 'modify.tags.massive'

    action = fields.Selection(selection=[('add','Agregar'),('delete','Quitar')])
    tag_ids = fields.Many2many(comodel_name='crm.tag')


    def action_done(self):
        lead_to_update_ids = self._context.get('active_ids', ['crm.lead'])
        for lead_to_update_id in lead_to_update_ids:
            lead = self.env['crm.lead'].browse(lead_to_update_id)
            for tag in self.tag_ids:
                lead.write({'tag_ids': [(4, tag.id)]}) if self.action == 'add' else lead.write({'tag_ids': [(3, tag.id)]})
        return False
        

