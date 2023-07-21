from odoo import fields, models

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    name = fields.Char(required=False)
    def create(self,vals):
        res = super(CrmLead,self).create(vals)
        for rec in res:
            if rec.name == 'custom_dev':
                name = res.contact_name or ''
                for tag in rec.intrest_tag_ids:
                    name += " | " + tag.name
                rec.name = name
        return res
    intrest_tag_ids = fields.Many2many(comodel_name='intrest.tag')




class IntrestTag(models.Model):
    _name = 'intrest.tag'

    name = fields.Char()
