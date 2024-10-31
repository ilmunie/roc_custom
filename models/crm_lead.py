from odoo import fields, models, api, SUPERUSER_ID, tools
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta

class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _order = 'datetime_in_stage,datetime_in_lead_stage desc'


    description_char = fields.Char(string="Notas (widget)")

    def edit_description(self):
        self.ensure_one()
        action = {
            'name': "Edicion notas",
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('roc_custom.crm_lead_quick_edit').id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': 'crm.lead',
            'target': 'new',
        }
        return action
    partner_child_ids = fields.One2many(related='partner_id.child_ids', readonly=False)

    def _prepare_address_values_from_partner(self, partner):
        # Sync all address fields from partner, or none, to avoid mixing them.
        return {}

    last_call_date = fields.Date(string='Fecha ultima llamada')
    last_call_status = fields.Selection(selection=[('no_aswer', 'Sin respuesta'), ('aswer', 'Atendida')], string="Estado ultima llamada")
    partner_vat = fields.Char(related='partner_id.vat')
    def copy(self, default=None):
        copied = super(CrmLead, self).copy(default)
        copied.autocomplete_name()
        return copied
    def _merge_opportunity(self, user_id=False, team_id=False, auto_unlink=True, max_length=5):
        act_automation_conf = self.env['activity.automation.config'].search([('model_id.model', '=', 'crm.lead')])
        unlink_lines = act_automation_conf.line_ids.filtered(lambda x: x.action_type == 'delete')
        act_types_to_delete = []
        for unlink_line in unlink_lines:
            act_types_to_delete.extend(unlink_line.activity_type_ids.mapped('id'))
        for record in self:
            record.activity_ids.filtered(lambda x: x.activity_type_id.id in act_types_to_delete).unlink()
        res = super()._merge_opportunity(user_id, team_id, auto_unlink, max_length)
        return res

    medium_written = fields.Boolean()
    force_close_date = fields.Datetime(string="Forzar cierre")
    date_closed = fields.Datetime(tracking=True)

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.partner_id:
                name += " | " + rec.partner_id.display_name
            res.append((rec.id, name))
        return res


    def compute_won_written(self):
        for record in self:
            if not record.won_written:
                if record.won_status == 'won':
                    record.won_written = True
                else:
                    record.won_written = False
    won_written = fields.Boolean(compute=compute_won_written, store=True)
#
    @api.constrains('won_status')
    def _check_won_accecss(self):
        for order in self:
            if order.won_written and not self.env.user.has_group('roc_custom.group_allow_modify_won_stage'):
                raise ValidationError("No esta autorizado a modificar un oportunidad ganada")
#
#



    def write(self, vals):
        res = super(CrmLead, self).write(vals)
        for record in self:
            if record.type == 'opportunity' and not record.date_conversion:
                record.date_conversion = fields.Datetime.now()
            if record.medium_id and not record.medium_written:
                record.medium_written = True
            if record.force_close_date and record.date_closed != record.force_close_date:
                record.date_closed = record.force_close_date
        return res

    def _merge_get_fields(self):
        res = super(CrmLead, self)._merge_get_fields()
        res.append('source_url')
        res.append('work_type_id')
        res.append('referred_professional')
        return res

    def _merge_data(self, fnames=None):
        res = super(CrmLead, self)._merge_data(fnames)
        values = self._merge_roconsa_fields()
        res.update(values)
        return res

    def _merge_roconsa_fields(self):
        opportunities = self
        values = {}
        values['company_concern'] = max(opportunities.filtered(lambda x: x.company_concern).mapped('company_concern')) if opportunities.filtered(lambda x: x.company_concern) else False
        values['customer_concern'] = max(opportunities.filtered(lambda x: x.customer_concern).mapped('customer_concern')) if opportunities.filtered(lambda x: x.customer_concern) else False
        if any(opportunity.safety_level == 'high' for opportunity in opportunities):
            values['safety_level'] = 'high'
        elif any(lead.safety_level == 'medium' for lead in opportunities):
            values['safety_level'] = 'medium'
        elif any(lead.safety_level == 'low' for lead in opportunities):
            values['safety_level'] = 'low'
        else:
            self.safety_level = opportunities[0].safety_level if opportunities else False

        if any(lead.type_of_contact == 'highly qualified' for lead in opportunities):
            values['type_of_contact'] = 'highly qualified'
        elif any(lead.type_of_contact == 'qualified' for lead in opportunities):
            values['type_of_contact'] = 'qualified'
        elif any(lead.type_of_contact == 'basic' for lead in opportunities):
            values['type_of_contact'] = 'basic'
        else:
            values['type_of_contact'] = opportunities[0].type_of_contact if opportunities else False

        if any(lead.type_of_client == 'vip' for lead in opportunities):
            values['type_of_client'] = 'vip'
        elif any(lead.type_of_client == 'preferential' for lead in opportunities):
            values['type_of_client'] = 'preferential'
        elif any(lead.type_of_client == 'profesional' for lead in opportunities):
            values['type_of_client'] = 'profesional'
        elif any(lead.type_of_client == 'standard' for lead in opportunities):
            values['type_of_client'] = 'standard'
        else:
            values['type_of_client'] = opportunities[0].type_of_client if opportunities else False

        values['installation'] = True if any(lead.installation for lead in opportunities) else False
        tags = []
        for lead in opportunities.filtered(lambda x: x.intrest_tag_ids):
            tags.extend(lead.intrest_tag_ids.mapped('id'))
        values['intrest_tag_ids'] = [(6, 0, tags)]
        tags = []
        for lead in opportunities.filtered(lambda x: x.tag_ids):
            tags.extend(lead.tag_ids.mapped('id'))
        values['tag_ids'] = [(6, 0, tags)]
        return values


    @api.depends('type')
    def followers_customization(self):
        for record in self:
            if record.type == 'lead':
                if self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False) and self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False).id not in record.message_follower_ids.mapped('partner_id.id'):
                    wiz = self.env['mail.wizard.invite'].create({'res_model':record._name, 'res_id':record.id})
                    wiz.write({'partner_ids': [(6,0, [self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False).id,])],'send_mail': False})
                    wiz.write({'partner_ids': [(6,0, [self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False).id,])],'send_mail': False})
                    wiz.add_followers()
            else:
                if self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False) and self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False).id in record.message_follower_ids.mapped('partner_id.id'):
                    record.message_follower_ids.filtered(lambda x: x.partner_id.id == self.env.ref('roc_custom.partner_lead_follower', raise_if_not_found=False).id)[0].unlink()
            record.trigger_followers_customization = False if record.trigger_followers_customization else True
    trigger_followers_customization = fields.Boolean(compute='followers_customization', store=True)
    def sync_expected_revenue(self):
        for record in self:
            amount = sum(record.order_ids.filtered(lambda x: not x.pos_order_line_ids and x.state in ('done', 'sale')).mapped('amount_untaxed'))
            pos_ids = []
            if record.order_ids:
                for pos_order_line in record.order_ids.pos_order_line_ids:
                    if pos_order_line.order_id.id not in pos_ids:
                        amount += (pos_order_line.order_id.amount_total - pos_order_line.order_id.amount_tax)
                        pos_ids.append(pos_order_line.order_id.id)
            record.expected_revenue = amount

    sale_amount_total = fields.Monetary(compute='_compute_sale_data', string="Sum of Orders", help="Untaxed Total of Confirmed Orders", currency_field='company_currency', store=True)
    quotation_count = fields.Integer(compute='_compute_sale_data', string="Number of Quotations", store=True)
    sale_order_count = fields.Integer(compute='_compute_sale_data', string="Number of Sale Orders", store=True)
    @api.depends('type')
    def autocomplete_name(self):
        for record in self:
            if record.type == 'opportunity':
                ir_sequences = self.env['ir.sequence'].search([('opportunity_sequence','=',True)])
                for sequence in ir_sequences:
                    domain_to_check = eval(sequence.opportunity_domain_to_check) if sequence.opportunity_domain_to_check else []
                    domain_to_check.insert(0,('id','=',record.id))
                    matching_rec = self.env['crm.lead'].search(domain_to_check)
                    if not matching_rec:
                        continue
                    else:
                        name = sequence.next_by_id()
                        record.name = name
                        break
            record.trigger_name_autocomplete = False if record.trigger_name_autocomplete else True
    trigger_name_autocomplete = fields.Boolean(compute=autocomplete_name, store=True, copy=False)
    @api.depends('lead_stage_change_ids')
    def compute_datetime_last_lead_stage(self):
        for record in self:
            if record.lead_stage_change_ids:
                record.datetime_in_lead_stage = sorted(record.lead_stage_change_ids, key=lambda r: r.date, reverse=True)[0].date #+ timedelta(days=1)
            else:
                record.datetime_in_lead_stage = record.create_date
    @api.depends('stage_change_ids')
    def compute_datetime_last_stage(self):
        for record in self:
            if record.stage_change_ids:
                record.datetime_in_stage = sorted(record.stage_change_ids, key=lambda r: r.date, reverse=True)[0].date #+ timedelta(days=1)
            else:
                record.datetime_in_stage = record.create_date


    datetime_in_lead_stage = fields.Datetime(compute=compute_datetime_last_lead_stage, store=True, string="Cambio de etapa lead")
    datetime_in_stage = fields.Datetime(compute=compute_datetime_last_stage, store=True, string="Cambio de etapa")
    lead_stage_change_ids = fields.One2many('crm.lead.stage.change','lead_id')
    stage_change_ids = fields.One2many('crm.stage.change','opportunity_id')



    @api.depends('stage_id')
    def trigger_crm_stage_change(self):
        for record in self:
            if record.stage_id:
                self.env['crm.stage.change'].create({
                    'opportunity_id': record.id,
                    'date': fields.Datetime.now(),
                    'stage_id': record.stage_id.id
                })

            record.trigger_crm_lead_stage_change = False if record.trigger_crm_lead_stage_change else True
    trigger_crm_stage_change = fields.Boolean(compute=trigger_crm_stage_change, store=True)

    @api.depends('lead_stage_id')
    def trigger_crm_lead_stage_change(self):
        for record in self:
            if record.lead_stage_id:
                self.env['crm.lead.stage.change'].create({
                    'lead_id': record.id,
                    'date': fields.Datetime.now(),
                    'lead_stage_id': record.lead_stage_id.id
                })

            record.trigger_crm_lead_stage_change = False if record.trigger_crm_lead_stage_change else True
    trigger_crm_lead_stage_change = fields.Boolean(compute=trigger_crm_lead_stage_change, store=True)
    @api.depends('message_ids')
    def get_last_message(self):
        for record in self:
            last_email_from_partner = False
            ##import pdb;pdb.set_trace()
            #if record.message_ids:
            #    last_message_id = sorted(record.message_ids.filtered(lambda x: x.body), key=lambda r: r.create_date, reverse=True)
            #    emails = []
            #    if record.partner_id:
            #        emails.append(record.partner_id.email)
            #    if record.email_from:
            #        emails.append(record.email_from)
            #    if last_message_id and last_message_id[0].email_from in emails:
            #        last_email_from_partner = True
            #if last_email_from_partner:
            #    if record.type == 'lead_id':
            #        stage = self.env['crm.lead.stage'].search([('name','=','Procesamiento Roconsa')])
            #        if stage:
            #            record.lead_stage_id = stage[0].id
            #    else:
            #        stage = self.env['crm.stage'].search([('name','=','Procesamiento Roconsa')])
            #        if stage:
            #            record.stage_id = stage[0].id

            record.last_email_from_partner = last_email_from_partner



    last_email_from_partner = fields.Boolean(compute=get_last_message, store=True)
    mobile_partner = fields.Char(related='partner_id.mobile', readonly=False, tracking=True, string="Móvil")

    def default_get(self, fields):
        res = super(CrmLead, self).default_get(fields)
        sorted_stages = self.env['crm.lead.stage'].search([], order='sequence', limit=1).mapped('id')
        res['lead_stage_id'] = sorted_stages[0] if sorted_stages else False
        return res

    @api.model
    def _read_group_lead_stage_ids(self, stages, domain, order):
        search_domain = []
        # perform search
        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)
    lead_stage_id = fields.Many2one('crm.lead.stage', string='Etapa Lead', index=True, tracking=True,copy=False, ondelete='restrict', group_expand='_read_group_lead_stage_ids')

    stage_id = fields.Many2one(
        'crm.stage', string='Stage', index=True, tracking=True,
        compute='_compute_stage_id', readonly=False, store=True,
        copy=False, group_expand='_read_group_stage_ids', ondelete='restrict',
        domain="[('excluded_team_ids', '!=', team_id),'|', ('team_id', '=', False), ('team_id', '=', team_id)]")

    def _stage_find(self, team_id=False, domain=None, order='sequence, id', limit=1):
        if self.team_id:
            if not domain:
                domain = [('excluded_team_ids', '!=', self.team_id.id)]
            else:
                domain.append(('excluded_team_ids', '!=', self.team_id.id))
        return super()._stage_find(team_id=team_id, domain=domain,order=order, limit=limit)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order):
        # retrieve team_id from the context and write the domain
        # - ('id', 'in', stages.ids): add columns that should be present
        # - OR ('fold', '=', False): add default columns that are not folded
        # - OR ('team_ids', '=', team_id), ('fold', '=', False) if team_id: add team columns that are not folded
        team_id = self._context.get('default_team_id')
        if team_id:
            search_domain = [('excluded_team_ids', '!=', team_id), ('active','=',True),'|', ('id', 'in', stages.ids), '|', ('team_id', '=', False), ('team_id', '=', team_id)]
        else:
            search_domain = [('active','=',True),'|', ('id', 'in', stages.ids), ('team_id', '=', False)]

        # perform search
        stage_ids = stages._search(search_domain, order=order, access_rights_uid=SUPERUSER_ID)
        return stages.browse(stage_ids)


    @api.model_create_multi
    def create(self, vals_list):
        lead_vals = []
        for vals in vals_list:
            if not vals.get('name', False):
                vals['name'] = "CONSULTA"
            if vals.get('technical_job_type_ref', False):
                self.create_ticket_from_leads(vals)
            else:
                if 'won_status' in vals and vals['won_status'] == 'won':
                    vals['won_written'] = True
                if 'medium_id' in vals and vals['medium_id']:
                    vals['medium_written'] = True
                if 'type' in vals and vals['type'] == 'odoo':
                    vals['type'] = 'lead'
                if 'sale_team_text' in vals and vals['sale_team_text']:
                    sale_teams = self.env['crm.team'].search([('name','ilike',vals['sale_team_text'])])
                    if sale_teams:
                        vals['team_id'] = sale_teams[0].id
                    else:
                        vals['team_id'] = self.env['crm.team'].create({'name': vals['sale_team_text']}).id
                if 'utm_medium_text' in vals and vals['utm_medium_text']:
                    mediums = self.env['utm.medium'].search([('name','ilike',vals['utm_medium_text'])])
                    if mediums:
                        vals['medium_id'] = mediums[0].id
                    else:
                        vals['medium_id'] = self.env['utm.medium'].create({'name': vals['utm_medium_text']}).id
                if 'utm_campaign_text' in vals and vals['utm_campaign_text']:
                    campaigns = self.env['utm.campaign'].search([('name','ilike',vals['utm_campaign_text'])])
                    if campaigns:
                        vals['campaign_id'] = campaigns[0].id
                    else:
                        vals['campaign_id'] = self.env['utm.campaign'].create({'name': vals['utm_campaign_text']}).id
                lead_vals.append(vals)
        return super(CrmLead, self).create(vals_list=lead_vals)

    def create_ticket_from_leads(self, ticket_val):
            team = self.env.ref('helpdesk.helpdesk_team1')
            partner_id = False
            email = ticket_val.get('email_from', False)
            ticket_type_name = ticket_val.get('technical_job_type_ref', False)
            mobile = ticket_val.get('mobile', False)
            contact_name = ticket_val.get('contact_name', False)
            priority_type_widget_data = ticket_val.get('priority_type_widget_data', False)
            if priority_type_widget_data == 'Si':
                customer_availability_widget_data = "- URGENTE -"
            else:
                customer_availability_widget_data = ""
            customer_availability_widget_data += ticket_val.get('customer_availability_widget_data', "")
            availability_type = 'no_data'
            if priority_type_widget_data and priority_type_widget_data == 'Si':
                availability_type = 'urgent'
            elif customer_availability_widget_data:
                availability_type = 'week_availability'
            availability_info = customer_availability_widget_data
            # Find or create partner based on email, mobile, or contact name
            if email:
                partner_id = self.env['res.partner'].search([('email', 'ilike', email)], limit=1)
            if not partner_id and mobile:
                partner_id = self.env['res.partner'].search(
                    ['|', ('mobile', 'ilike', mobile), ('phone', 'ilike', mobile)], limit=1)
            if not partner_id and contact_name:
                partner_id = self.env['res.partner'].search([('name', 'ilike', contact_name)], limit=1)

            # Find or create ticket type based on name
            ticket_type_id = self.env['helpdesk.ticket.type'].search([('name', '=', ticket_type_name)], limit=1)
            if not ticket_type_id:
                ticket_type_id = self.env['helpdesk.ticket.type'].create({'name': ticket_type_name})
            # Append ticket values as a tuple for SQL insertion
            val = {
                'name': f"TICKET {contact_name} - {ticket_type_name}" ,
                'partner_id': partner_id[0].id if partner_id else False,
                'partner_name': f"{partner_id[0].name} - {contact_name}" if partner_id else contact_name,
                'partner_email': email,
                'partner_mobile': mobile,
                'partner_phone': mobile,
                'visit_internal_notes': customer_availability_widget_data,
                'ticket_type_id': ticket_type_id.id if ticket_type_id else False,
                'team_id': team.id,
                'customer_availability_info': availability_info,
                'customer_availability_type': availability_type,
                'stage_id': self.env.ref('helpdesk.stage_new').id,
                'description': ticket_val.get('description_char', False),
                'source_url': ticket_val.get('source_url', False)
            }
            self.env['helpdesk.ticket'].create(val)
            return True

    source_url = fields.Char(
        string="URL de procedencia",
    )
    work_type_id = fields.Many2one(
        string="Tipo de obra",
        comodel_name='crm.work.type', tracking=True
    )

    stage_name = fields.Char(related="stage_id.name")
    company_concern = fields.Selection([
        ('0', 'No establecido'),
        ('1', 'Bajo'),
        ('2', 'Normal'),
        ('3', 'Alto'),
        ('4', 'Muy Alto'),
        ('5', 'Urgente')],
        string="Interés Roconsa", tracking=True
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

    utm_medium_text = fields.Char(string="Medio Txt")
    utm_campaign_text = fields.Char(string="Campaña Txt")
    sale_team_text = fields.Char(string="Equipo de ventas Txt")

    referred_professional = fields.Many2one('res.partner', domain=[('professional','=',True)], string="Profesional vinculado")

    @api.depends('type')
    def compute_team_custom(self):
        res = super(CrmLead, self)._compute_team_id()
        return res

    team_id = fields.Many2one(
        'crm.team', 'Sales Team',
        ondelete="set null", tracking=True, compute=compute_team_custom)
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
            record.phone_resume = res.replace(" ", "")
    phone_resume = fields.Char(string="Teléfono/Móvil",compute="compute_phone_resume", store=True)


    def _get_lead_duplicates_custom(self, partner=None, email=None, phone=None, mobile=None, include_lost=False):
        """ Search for leads that seem duplicated based on partner / email.

        :param partner : optional customer when searching duplicated
        :param email: email (possibly formatted) to search
        :param boolean include_lost: if True, search includes archived opportunities
          (still only active leads are considered). If False, search for active
          and not won leads and opportunities;
        """
        if not email and not partner and not phone and not mobile:
            return self.env['crm.lead']

        domain = []
        for normalized_email in [tools.email_normalize(email) for email in tools.email_split(email)]:
            domain.append(('email_normalized', '=', normalized_email))
        if partner:
            domain.append(('partner_id', '=', partner.id))

        tel_vec = []
        if mobile:
            tel_vec.append(mobile)
        if phone:
            tel_vec.append(phone)
        if tel_vec:
            domain.append(('phone', 'in', tel_vec))
            domain.append(('mobile', 'in', tel_vec))

        if not domain:
            return self.env['crm.lead']

        domain = ['|'] * (len(domain) - 1) + domain
        if include_lost:
            domain += ['|', ('type', '=', 'opportunity'), ('active', '=', True)]
        else:
            domain += ['&', ('active', '=', True), '|', ('stage_id', '=', False), ('stage_id.is_won', '=', False)]
        if domain:
            domain.insert(0, ('id', 'not in', self.mapped('id')))
            domain.insert(0, '&')
        return self.with_context(active_test=False).search(domain)


    @api.depends('email_from', 'partner_id', 'contact_name', 'partner_name', 'phone', 'mobile')
    def _compute_potential_lead_duplicates(self):
        res = super(CrmLead, self)._compute_potential_lead_duplicates()
        for record in self:
            tel_vec = []
            if record.mobile:
                tel_vec.append(record.mobile)
            if record.phone:
                tel_vec.append(record.phone)
            if tel_vec:
                other_opp = self.env['crm.lead'].search([('id', '!=', record._origin.id),'|', ('phone','in',tel_vec), ('mobile','=',tel_vec)])
                for opp in other_opp:
                    record.duplicate_lead_ids = [(4,opp.id)]
            record.duplicate_lead_ids = [(3,record.id)]
            record.duplicate_lead_count = len(record.duplicate_lead_ids)
        return res