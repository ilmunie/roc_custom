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



