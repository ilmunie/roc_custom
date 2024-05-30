from odoo import fields, models, api
from odoo.osv import expression

class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    @api.depends('attribute_id', 'attribute_id.name', 'name')
    def get_search_name(self):
        for record in self:
            record.search_name = record.display_name
    search_name = fields.Char(compute=get_search_name, store=True)
    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if operator == 'ilike':
            domain = [('search_name', 'ilike', name)]
            return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid)