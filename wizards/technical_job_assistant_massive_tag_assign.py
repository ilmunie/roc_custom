from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta


class TechnicalJobAssistantMassiveTagAssign(models.TransientModel):
    _name = 'technical.job.assistant.massive.tag.assign'

    tag_ids = fields.Many2many('technical.job.tag', 'tja_masive_tag_assign_rel','ass_id','tag_id', required=True)

    def action_done(self):
        active_jobs = self.env['technical.job.assistant'].browse(self._context.get('active_ids', []))
        if not active_jobs:
            return
        for active_job in active_jobs:
            for tag in self.tag_ids:
                active_job.technical_job_tag_ids = [(4, tag.id)]
        return False

