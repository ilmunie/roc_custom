from odoo import fields, models, api
import json

class TechnicalJobChecklistConfig(models.Model):
    _name = 'technical.job.checklist.config'

    matching_domain = fields.Char(string="Condiciones Operacion")
    name = fields.Char(string="Nombre")
    line_ids = fields.One2many('technical.job.checklist.config.line', 'config_id', copy=True)

class TechnicalJobChecklistConfigLine(models.Model):
    _name = 'technical.job.checklist.config.line'

    sequence = fields.Integer(string="Secuencia")
    config_id = fields.Many2one('technical.job.checklist.config')
    question = fields.Char(string="Pregunta")
    answer_type = fields.Selection(selection=[('yes_no','Si/No'), ('text', 'Text')], string="Tipo respuesta")


class TechnicalChecklistAssistant(models.TransientModel):
    _name = "technical.job.checklist.assistant"

    def get_lines(self, technical_job):
        config_lines = []
        result_lines_ids = technical_job.checklist_line_ids.mapped('id')
        for checklist_config in self.env['technical.job.checklist.config'].search([]):
            domain = json.loads(checklist_config.matching_domain)
            domain.insert(0, ('id', '=', technical_job.id))
            if self.env['technical.job'].search_count(domain) > 0:
                config_lines.extend(checklist_config.line_ids.filtered(lambda x: x.id not in technical_job.checklist_line_ids.mapped('checklist_config_line_id.id')).mapped('id'))
        vals_to_create = []
        for config_line in config_lines:
            vals_to_create.append({
                'technical_schedule_id': technical_job.schedule_id.id,
                'checklist_config_line_id': config_line,
            })
        if vals_to_create:
            result_lines_ids.extend(self.env['technical.job.checklist.assistant.line'].create(vals_to_create).mapped('id'))
        return result_lines_ids

    technical_job_id = fields.Many2one('technical.job')

    checklist_id = fields.Many2one('technical.job.checklist.config')

    @api.depends('line_ids')
    def get_checklist_domain(self):
        for record in self:
            res = []
            if record.line_ids:
                res = record.line_ids.mapped('checklist_config_line_id.config_id.id')
            res = [('id', 'in', res)]
            record.checklist_domain = json.dumps(res)
    checklist_domain = fields.Char(compute=get_checklist_domain)

    @api.onchange('checklist_id')
    def onchange_checklist_id(self):
        self.ensure_one()
        lines = []
        if self.checklist_id:
            lines = self.line_ids.filtered(lambda x: x.checklist_config_line_id.config_id.id == self.checklist_id.id).mapped('id')
        self.filtered_line_ids = [(6, 0, lines)]


    filtered_line_ids = fields.Many2many(
        comodel_name="technical.job.checklist.assistant.line",
        relation="checklist_asistant_wiz_line_filtered",
        column1="wiz_id",
        column2="line_id",
    )

    line_ids = fields.Many2many(
        comodel_name="technical.job.checklist.assistant.line",
        relation="checklist_asistant_wiz_line",
        column1="wiz_id",
        column2="line_id",
    )
    @api.model
    def default_get(self, fields):
        result = super(TechnicalChecklistAssistant, self).default_get(fields)
        result['technical_job_id'] = self.env.context.get("technical_job", False)
        technical_job = self.env['technical.job'].browse(result['technical_job_id'])
        result['line_ids'] = [(6, 0, self.get_lines(technical_job))]
        return result

    def action_done(self):
        return False


class TechnicalChecklistAssistantLine(models.Model):
    _name = "technical.job.checklist.assistant.line"

    technical_schedule_id = fields.Many2one('technical.job.schedule')
    checklist_config_line_id = fields.Many2one('technical.job.checklist.config.line')
    sequence = fields.Integer(related="checklist_config_line_id.sequence")
    question = fields.Char(related="checklist_config_line_id.question")
    answer_type = fields.Selection(related="checklist_config_line_id.answer_type")
    yes_no_answer = fields.Selection(selection=[('yes','Si'), ('no', 'No')])
    text_answer = fields.Text()

