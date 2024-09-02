from odoo import fields, models, api

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    technical = fields.Boolean()
    technical_time_sale_line_product_id = fields.Many2one('product.product', string="Linea venta MO trabajo tecnico")

class HrEmployePublic(models.Model):
    _inherit = 'hr.employee.public'

    technical = fields.Boolean()