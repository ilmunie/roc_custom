from odoo import fields, models, api


class TechnicalJobMovementWizard(models.TransientModel):
    _name = "technical.job.movement.wizard"

class TechnicalJobTimeRegister(models.Model):
    _name = "technical.job.time.register"

    displacement = fields.Boolean(string="Desplazamiento")
    technical_job_schedule_id = fields.Many2one('technical.job.schedule', string="Operacion")

    @api.depends('start_time', 'end_time')
    def compute_total_min(self):
        for record in self:
            res = 0
            if record.start_time and record.end_time:
                res = (record.end_time - record.start_time).total_seconds()/60
            record.total_min = res

    total_min = fields.Float(compute=compute_total_min, store=True, string="Minutos")
    start_time = fields.Datetime(string="Inicio")
    end_time = fields.Datetime(string="Fin")