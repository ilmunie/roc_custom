from odoo import fields, models

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    intrest_tag_ids = fields.Many2many(comodel_name='intrest.tag')


class IntrestTag(models.Model):
    _name = 'intrest.tag'

    name = fields.Char()
