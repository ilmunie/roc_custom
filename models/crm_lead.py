from odoo import fields, models, api


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    @api.depends('name')
    def compute_name(self):
        for record in self:
            if record.name == 'custom_dev':
                name = record.contact_name or ''
                for tag in record.intrest_tag_ids:
                    name += " | " + tag.name
                record.name = name
            record.trigger_change_name = False if record.trigger_change_name else True
    trigger_change_name = fields.Boolean(compute='compute_name', store=True)

    intrest_tag_ids = fields.Many2many(comodel_name='intrest.tag')


class IntrestTag(models.Model):
    _name = 'intrest.tag'

    name = fields.Char()
