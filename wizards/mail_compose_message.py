import json

from odoo import api, fields, models, _


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def default_get(self, fields):
        result = super(MailComposeMessage, self).default_get(fields)
        model = result['model'] if 'model' in result else False
        if model == 'crm.lead':
            template_id = self.env.ref('roc_custom.mail_template_lead_req').id
            result['template_id'] = template_id
        return result


    @api.depends('res_id')
    def compute_child_ids(self):
        for record in self:
            show_child = False
            domain = [('id', '=', 0)]
            if record.model == 'crm.lead':
                rec = self.env[record.model].browse(record.res_id)
                if rec.partner_id and rec.partner_id.child_ids.ids:
                    domain = ['|',('id', '=', rec.partner_id.id), ('id', 'in', rec.partner_id.child_ids.ids)]
                    show_child = True
            record.child_ids_domain = json.dumps(domain)
            record.show_child_ids = True

    show_child_ids = fields.Boolean(compute=compute_child_ids)
    child_ids_domain = fields.Char(compute=compute_child_ids)
    child_ids = fields.Many2many('res.partner', 'mcm_pchild_ids_rel', 'wiz_id', 'partner_id', string="Contactos Alternativos")

    @api.onchange('child_ids')
    def onchange_child_ids(self):
        for child in self.child_ids:
            self.partner_ids = [(4, child.id)]


