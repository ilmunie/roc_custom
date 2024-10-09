from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta


class TechnicalJobAssistantQuickCreate(models.TransientModel):
    _name = 'technical.job.assistant.quick.create'

    default_datetime = fields.Datetime(string="Fecha por defecto", required=True)
    set_stand_by_to_draft = fields.Boolean(string="Stand-by a Borrador")


    def action_done(self):
        active_jobs = self.env['technical.job.assistant'].browse(self._context.get('active_ids', []))
        if not active_jobs:
            return
        vals_to_create = []
        for active_job in active_jobs:
            if active_job.next_active_job_id:
                active_job.next_active_job_id.date_schedule = self.default_datetime
                if self.set_stand_by_to_draft and active_job.next_active_job_id.job_status == 'stand_by':
                    active_job.next_active_job_id.job_status = "to_do"
            else:
                real_rec = self.env[active_job.res_model].browse(active_job.res_id)
                real_rec.write({'technical_schedule_job_ids': [(0, 0, {
                    'res_model': real_rec._name,
                    'res_id': real_rec.id})]})
                vals_to_create.append({
                    'date_schedule': self.default_datetime,
                    'res_id': active_job.res_id,
                    'res_model': active_job.res_model,
                    'job_type_id': active_job.config_id.technical_job_type_id.id,
                    'schedule_id': real_rec.technical_schedule_job_ids.filtered(lambda x: not x.date_schedule)[0].id,
                    'user_id': active_job.config_id.responsible_user_id.id
                })
        self.env['technical.job'].create(vals_to_create)
        action = self.env["ir.actions.actions"]._for_xml_id("roc_custom.action_technical_job")
        action['context'] = {
            'default_mode': "week",
            'initial_date': self.default_datetime.date(),
        }
        return action

