from odoo import fields, models, api
from lxml import etree


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _order = 'create_date desc'


    work_type_id = fields.Many2one('crm.work.type', tracking=True)
    source_id = fields.Many2one('utm.source', tracking=True)
    priority = fields.Selection(tracking=True)
    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += ['|', ('email', 'ilike', name),'|', ('street', 'ilike', name), '|', ('phone', 'ilike', name), '|', ('mobile', 'ilike', name), ('name', 'ilike', name)]

            name = ''
        return super(CrmLead, self).name_search(name=name, args=args, operator=operator, limit=limit)
    def _find_matching_partner(self, email_only=False):
        """ Try to find a matching partner with available information on the
        lead, using notably customer's name, email, ...

        :param email_only: Only find a matching based on the email. To use
            for automatic process where ilike based on name can be too dangerous
        :return: partner browse record
        """
        self.ensure_one()
        partner = self.partner_id

        if not partner and self.email_from:
            partner = self.env['res.partner'].search([('email', '=', self.email_from),('email','not in',('noreply@chatwith.io','noreply@secretariado-online.com'))], limit=1)
        if not partner and (self.phone or self.mobile):
            contact_numbers = []
            if self.phone:
                contact_numbers.append(self.phone)
            if self.mobile:
                contact_numbers.append(self.mobile)
            partner = self.env['res.partner'].search(['|',('phone', 'in', contact_numbers),('mobile', 'in', contact_numbers)], limit=1)

        if not partner:
            # search through the existing partners based on the lead's partner or contact name
            # to be aligned with _create_customer, search on lead's name as last possibility
            for customer_potential_name in [self[field_name] for field_name in ['partner_name', 'contact_name', 'name'] if self[field_name]]:
                partner = self.env['res.partner'].search([('name', 'ilike', '%' + customer_potential_name + '%')], limit=1)
                if partner:
                    break

        return partner

    #def extract_data_form_html(self, message):
    #    html_body = message[0].body
    #    html_data = {}
    #    try:
    #        root = etree.fromstring(html_body, parser=etree.HTMLParser())
    #        table = root.xpath("//table[@style='border:0; margin:10px 0']")
    #        if table:
    #            rows = table[0].xpath(".//tr")
    #            for row in rows:
    #                cells = row.xpath(".//td")
    #                if len(cells) == 2:
    #                    label = cells[0].text.strip()
    #                    value = cells[1].text.strip()
    #                    html_data[label] = value
    #    except Exception as e:
    #        print("Error:", e)
#
    #    vals_to_write = {}
    #    mail_from = message[0].email_from
    #    #if mail_from == 'noreply@secretariado-online.com':
    #    #    False
    #    if mail_from == 'noreply@chatwith.io':
    #        vals_to_write = {
    #            'name': 'Llamada de ' + html_data['Nombre'] if html_data['Nombre'] else 'Se ha',
    #            'contact_name': html_data['Nombre'],
    #            'mobile': html_data['Número WhatsApp'],
    #            'zip': html_data['Código postal'],
    #            'email_from': html_data['Email'],
    #        }
    #    return vals_to_write
    #@api.depends('create_date')
    #def extract_data(self):
    #    for record in self:
    #        if not record.contact_name and not record.partner_id:
    #            create_message = record.message_ids.filtered(lambda x: x.email_from in ('noreply@chatwith.io','noreply@secretariado-online.com'))
    #            if create_message:
    #                    vals_to_write = record.extract_data_form_html(create_message)
    #                    if vals_to_write:
    #                        record.write(vals_to_write)
    #        record.trigger_extract_data = False if record.trigger_extract_data else True
#
    #trigger_extract_data = fields.Boolean(compute=extract_data, store=True)
    @api.depends('name')
    def compute_name(self):
        for record in self:
            if record.name == 'custom_dev':
                if not record.partner_id:
                    name = record.contact_name or ''
                else:
                    name = record.partner_id.name
                for tag in record.intrest_tag_ids:
                    name += " | " + tag.name
                record.name = name
            record.trigger_change_name = False if record.trigger_change_name else True
    trigger_change_name = fields.Boolean(compute='compute_name', store=True)

    intrest_tag_ids = fields.Many2many(comodel_name='intrest.tag',tracking=True)

    @api.depends('phone','mobile')
    def compute_phone_resume(self):
        for record in self:
            res = ''
            if record.mobile:
                res = record.mobile
            if record.phone and record.phone!=record.mobile :
                if len(res)>1:
                    res += '/'
                res+= record.phone
            record.phone_resume = res
    phone_resume = fields.Char(string="Contacto",compute="compute_phone_resume")
    lost_reason_id = fields.Many2one(
        'lead.lost.reason', string='Motivo de la pérdida', index=True, tracking=True)
    lost_observations = fields.Text(string='Aclaraciones pérdida', tracking=True)
