from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def default_get(self, fields):
        #import pdb;pdb.set_trace()
        res = super(ResPartner, self).default_get(fields)
        lead_id = self.env.context.get('active_id',False)
        if lead_id:
            lead = self.env['crm.lead'].browse(lead_id)
            if lead:
                vals = lead._prepare_customer_values(self)
                vals['name'] = lead.contact_name if lead.contact_name else lead.email_from
                res.update(vals)
        return res

    default_purchase_picking_type_id = fields.Many2one('stock.picking.type', string="Recibir en")
    phone = fields.Char(widget="phone")
    mobile = fields.Char(widget="mobile")
    professional = fields.Boolean(string="Profesional")
    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += ['|', ('email', 'ilike', name),'|', ('street', 'ilike', name), '|', ('phone', 'ilike', name), '|', ('mobile', 'ilike', name), '|', ('vat', 'ilike', name), ('name', 'ilike', name)]

            name = ''
        return super(ResPartner, self).name_search(name=name, args=args, operator=operator, limit=limit)
