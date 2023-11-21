from odoo import fields, models, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    technical = fields.Boolean()