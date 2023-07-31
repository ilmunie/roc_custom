from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    phone = fields.Char(widget="phone")
    mobile = fields.Char(widget="mobile")

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += ['|', ('email', 'ilike', name),'|', ('street', 'ilike', name), '|', ('phone', 'ilike', name), '|', ('mobile', 'ilike', name), '|', ('vat', 'ilike', name), ('name', 'ilike', name)]

            name = ''
        return super(ResPartner, self).name_search(name=name, args=args, operator=operator, limit=limit)