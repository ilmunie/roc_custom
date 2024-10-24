from odoo import fields, models, api, SUPERUSER_ID
from random import randint


class TechnicalJobCateg(models.Model):
    _name = "technical.job.categ"

    name = fields.Char('Categoria', required=True)

class TechnicalJobTag(models.Model):
    _name = "technical.job.tag"
    _description = "Technical Job Tag"

    def _get_default_color(self):
        return randint(1, 11)

    name = fields.Char('Tag Name', required=True, translate=True)
    color = fields.Integer('Color', default=_get_default_color)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]

class TechnicalJobType(models.Model):
    _name = 'technical.job.type'

    name = fields.Char(string="Name")
    default_duration_hs = fields.Float(string="Duración Hs")
    default_job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita", domain=[('technical','=',True)])
    default_job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")
    allow_displacement_tracking = fields.Boolean(default=True, string="Cronometrar Desplazamiento?")
    requires_documentation = fields.Boolean(default=True, string="Tecnico: Requiere Documentacion?")
    data_assistant = fields.Boolean(default=True, string="Asistente Finalizacion?")
    force_time_registration = fields.Boolean(default=True, string="Tecnico: Forzar registro de tiempo")