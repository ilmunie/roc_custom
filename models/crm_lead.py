from odoo import fields, models, api
from lxml import etree
from datetime import timedelta


class CrmWorkType(models.Model):
    _name = 'crm.work.type'
    _description = 'Tipo de obra'

    name = fields.Char(
        string="Tipo de obra",
    )

class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _order = 'create_date desc'


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'type' in vals and vals['type'] == 'odoo':
                vals['type'] = 'lead'            
        #import pdb;pdb.set_trace()
        res = super(CrmLead, self).create(vals_list=vals_list)
        return res
#aux field
    source_url = fields.Char(
        string="URL de procedencia",
    )
    work_type_id = fields.Many2one(
        string="Tipo de obra",
        comodel_name='crm.work.type', tracking=True
    )
    customer_concern = fields.Selection([
        ('low', 'Bajo'),
        ('medium', 'Medio'),
        ('high', 'Alto')],
        string="Interés del cliente", tracking=True
    )
    installation = fields.Boolean(
        string="¿Busca instalación?",
        default=False, tracking=True
    )
    type_of_client = fields.Selection([
        ('standard', 'Estándar'),
        ('profesional', 'Profesional'),
        ('preferential', 'Preferente'),
        ('vip', 'VIP')],
        string="Tipo de cliente", tracking=True
    )
    type_of_contact = fields.Selection([
        ('basic', 'Contacto básico'),
        ('qualified', 'Contacto cualificado'),
        ('highly qualified', 'Contacto muy cualificado')],
        string="Tipo de contacto", tracking=True
    )
    safety_level = fields.Selection([
        ('low', 'Bajo'),
        ('medium', 'Medio'),
        ('high', 'Alto')],
        string="Nivel de seguridad", tracking=True
    )
    def action_view_sale_quotation(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action['context'] = {
            'search_default_draft': 1,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_opportunity_id': self.id
        }
        action['domain'] = [('opportunity_id', '=', self.id), ('state', 'in', ['draft', 'sent'])]
        quotations = self.mapped('order_ids').filtered(lambda l: l.state in ('draft', 'sent'))
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = quotations.id
        return action
    @api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_sale_data(self):
        for lead in self:
            total = 0.0
            quotation_cnt = 0
            sale_order_cnt = 0
            company_currency = lead.company_currency or self.env.company.currency_id
            for order in lead.order_ids:
                if order.state in ('draft', 'sent'):
                    quotation_cnt += 1
                if order.state not in ('draft', 'sent', 'cancel'):
                    sale_order_cnt += 1
                    total += order.currency_id._convert(
                        order.amount_total, company_currency, order.company_id, order.date_order or fields.Date.today())
            lead.sale_amount_total = total
            lead.quotation_count = quotation_cnt
            lead.sale_order_count = sale_order_cnt
    @api.depends('order_ids','order_ids.invoice_ids')
    def get_sam(self):
        for record in self:
            am = []
            for so in record.order_ids:
                if so.invoice_ids:
                    am.extend(so.invoice_ids.mapped('id'))
            record.sale_account_move_ids = [(6,0,am)]

    sale_account_move_ids = fields.Many2many(comodel_name='account.move', compute=get_sam, store=True)

    def action_open_so_account_move(self):
            invoices = self.mapped('sale_account_move_ids')
            action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
            if len(invoices) > 1:
                action['domain'] = [('id', 'in', invoices.ids)]
            elif len(invoices) == 1:
                form_view = [(self.env.ref('account.view_move_form').id, 'form')]
                if 'views' in action:
                    action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
                else:
                    action['views'] = form_view
                action['res_id'] = invoices.id
            else:
                action = {'type': 'ir.actions.act_window_close'}
            return action
    def action_open_so_account_move_unpaid(self):
        invoices = self.mapped('sale_account_move_ids')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        context = {
            'search_default_filter_open': '1',
        }
        action['context'] = context
        return action
    def compute_sale_move_values(self):
        for record in self:
            invoice_count = 0
            invoice_total_amount = 0
            invoice_unpaid_count = 0
            invoice_unpaid_amount = 0
            if record.sale_account_move_ids:
                invoice_count = len(record.sale_account_move_ids.filtered(lambda x: x.state == 'posted') or [])
                invoice_total_amount = sum(record.sale_account_move_ids.filtered(lambda x: x.state == 'posted').mapped('amount_total_signed') or [])
                invoice_unpaid_count = len(record.sale_account_move_ids.filtered(lambda x: x.state == 'posted' and x.amount_residual > 0) or [])
                invoice_unpaid_amount = sum(record.sale_account_move_ids.filtered(lambda x: x.state == 'posted' and x.amount_residual > 0).mapped('amount_residual') or [])
            record.invoice_count = invoice_count
            record.invoice_total_amount = invoice_total_amount
            record.invoice_unpaid_count = invoice_unpaid_count
            record.invoice_unpaid_amount = invoice_unpaid_amount

    invoice_count = fields.Integer(compute=compute_sale_move_values)
    invoice_total_amount = fields.Float(compute=compute_sale_move_values)
    invoice_unpaid_count = fields.Integer(compute=compute_sale_move_values)
    invoice_unpaid_amount = fields.Float(compute=compute_sale_move_values)

    @api.depends('date_schedule_visit','date_visited','visited')
    def get_calendar_date(self):
        for record in self:
            if record.visited:
                res = record.date_visited
            else:
                res = record.date_schedule_visit
            record.calendar_date = res

    calendar_date = fields.Datetime(compute=get_calendar_date, store=True)
    date_schedule_visit = fields.Datetime(string="A visitar")
    visit_duration = fields.Float(string="Tiempo visita (hs.)")
    visited = fields.Boolean(string="Visita terminada")
    date_visited = fields.Datetime(string="Visitado el")
    visit_user_ids = fields.Many2many(comodel_name='res.users', string="Personal visita")
    visit_vehicle = fields.Many2one('fleet.vehicle', string="Vehículo")
    crm_lead_visit_ids = fields.One2many('crm.lead.visit','lead_id')
    @api.depends('visited','date_schedule_visit')
    def get_visit_status(self):
        for record in self:
            if record.visited:
                res = f"Visitado"
            elif record.date_schedule_visit:
                res = f"A visitar"
            else:
                res = "Sin visitas programadas"
            record.visit_status = res

    visit_status = fields.Char(compute=get_visit_status, store=True, string="Estado visita")
    @api.depends('visited','date_schedule_visit')
    def get_visit_status(self):
        for record in self:
            if record.visited:
                res = f"Visitado el {record.date_visited.strftime('%Y-%m-%d') or ''}"
            elif record.date_schedule_visit:
                res = f"A visitar {record.date_schedule_visit.strftime('%Y-%m-%d') or ''}"
            else:
                res = "Sin visitas programadas"
            record.visit_status_date = res

    visit_status_date = fields.Char(compute=get_visit_status, store=True, string="Estado visita")
    @api.depends('visit_user_ids')
    def recompute_visit_calendar(self):
        for record in self:
            record.crm_lead_visit_ids.unlink()
            create_vals = []
            for user in record.visit_user_ids:
                vals = {
                    'lead_id': record.id,
                    'visit_user_id': user.id,
                }
                create_vals.append(vals)
            self.env['crm.lead.visit'].create(create_vals)
            res = False if record.trigger_recompute_visit_calendar else True
            record.trigger_recompute_visit_calendar = res



    trigger_recompute_visit_calendar = fields.Boolean(compute='recompute_visit_calendar', store=True)

    def write(self, vals):
        res = super(CrmLead, self).write(vals)
        if 'visited' in vals and vals['visited']:
            self.date_visited = fields.datetime.now()
        return res



    partner_street = fields.Char(related='partner_id.street', readonly=False)
    partner_street2 = fields.Char(related='partner_id.street2', readonly=False)
    partner_zip = fields.Char(related='partner_id.zip', readonly=False)
    partner_city = fields.Char(related='partner_id.city', readonly=False)
    partner_state_id = fields.Many2one(related='partner_id.state_id', readonly=False)
    partner_country_id = fields.Many2one(related='partner_id.country_id', readonly=False)
    partner_lang = fields.Selection(related='partner_id.lang', readonly=False)

    referred_professional = fields.Many2one('res.partner', domain=[('professional','=',True)], string="Profesional vinculado")

    team_id = fields.Many2one(
        'crm.team', 'Sales Team',
        ondelete="set null", tracking=True)
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        return False

    def get_link_html(self):
        for record in self:
            html = ""
            html += "<table>"
            html += "<tr><td><a href='/web#id={}&view_type=form&model={}'target='_blank'>".format(record.id, 'crm.lead')
            html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(" Ver ")
            record.link_to_form = html
    link_to_form = fields.Html(compute=get_link_html)

    source_id = fields.Many2one('utm.source', tracking=True)
    priority = fields.Selection(tracking=True)
    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += ['|', ('email_from', 'ilike', name),'|', ('street', 'ilike', name), '|', ('phone', 'ilike', name), '|', ('mobile', 'ilike', name), ('name', 'ilike', name)]

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

