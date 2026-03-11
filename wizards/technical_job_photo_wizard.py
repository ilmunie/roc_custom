from odoo import fields, models, api


class TechnicalJobPhotoWizard(models.TransientModel):
    _name = 'technical.job.photo.wizard'
    _description = 'Wizard para carga de fotos de operacion'

    technical_job_id = fields.Many2one('technical.job')
    photo_stage = fields.Selection([
        ('initial', 'Fotos Iniciales'),
        ('final', 'Fotos Finales')
    ], string="Tipo de Fotos")
    photo_ids = fields.Many2many('ir.attachment', string="Fotos")

    @api.model
    def default_get(self, fields_list):
        result = super().default_get(fields_list)
        result['technical_job_id'] = self.env.context.get('technical_job', False)
        result['photo_stage'] = self.env.context.get('photo_stage', False)
        return result

    def action_done(self):
        job = self.technical_job_id
        if self.photo_ids:
            res_model = 'technical.job.schedule' if not job.schedule_id.res_model else job.schedule_id.res_model
            res_id = job.schedule_id.id if not job.schedule_id.res_model else job.schedule_id.res_id
            self.photo_ids.write({
                'res_model': res_model,
                'res_id': res_id,
                'added_from_technical_job': True,
                'photo_stage': self.photo_stage,
            })
        if self.photo_stage == 'final':
            result = job.mark_as_done()
            if isinstance(result, dict):
                return result
        return {'type': 'ir.actions.act_window_close'}
