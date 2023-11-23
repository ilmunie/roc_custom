from odoo import fields, models, api

class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    opportunity_sequence = fields.Boolean()
    opportunity_domain_to_check = fields.Char()