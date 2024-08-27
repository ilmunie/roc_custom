from odoo import fields, models, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    technical = fields.Boolean()
    technical_time_sale_line_description = fields.Text()

class HrEmployePublic(models.Model):
    _inherit = 'hr.employee.public'

    technical = fields.Boolean()