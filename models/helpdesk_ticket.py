from odoo import fields, models, api, tools
import json
from odoo.osv import expression
from odoo.addons.iap.tools import iap_tools

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ticket_id = fields.Many2one('helpdesk.ticket', string="Ticket")

class HelpDeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    @api.depends('visit_internal_notes')
    def translate_html_internal_notes(self):
        for record in self:
            record.visit_internal_notes_html = record.visit_internal_notes.replace('\n', '<br/>') if record.visit_internal_notes else False

    visit_internal_notes_html = fields.Html(compute=translate_html_internal_notes, string='Nota tecnico')
    def edit_desctiption(self):
        self.ensure_one()
        action = {
            'name': "Edicion descripcion ticket",
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('roc_custom.quick_description_edit_ticket').id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': 'helpdesk.ticket',
            'target': 'new',
        }
        return action

    def edit_visit_note(self):
        self.ensure_one()
        action = {
            'name': "Nota a técnico",
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('roc_custom.quick_visit_note_edit_ticket').id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': 'helpdesk.ticket',
            'target': 'new',
        }
        return action

    def view_form_view(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "views": [[False, "form"]],
        }

    source_url = fields.Char(
        string="URL de procedencia",
    )

    def write(self, vals):
        res = super(HelpDeskTicket, self).write(vals)
        for record in self:
            opportunity_id = record.res_id if record.res_model == 'crm.lead' else False
            if not opportunity_id and record.res_model == 'sale.order':
                if record.src_rec and record.src_rec.opportunity_id:
                    opportunity_id = record.src_rec.opportunity_id.id
            if opportunity_id:
                for order in record.order_ids:
                    order.opportunity_id = opportunity_id
        return res

    def action_view_sale_quotation(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_quotations_with_onboarding")
        action['context'] = {
            'search_default_draft': 1,
        }
        quotations = self.mapped('order_ids')
        if self.src_rec:
            quotations += self.src_rec.order_ids
            other_tickets = self.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != self.id)
            for ticket in other_tickets:
                quotations += ticket.mapped('order_ids')
        action['domain'] = [ ('id', 'in', quotations.mapped('id'))]
        if len(quotations) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = quotations.id
        return action

    def action_view_sale_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        action['context'] = {
            'search_default_sales': 1,
        }
        orders = self.mapped('order_ids')
        if self.src_rec:
            orders += self.src_rec.order_ids
            other_tickets = self.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != self.id)
            for ticket in other_tickets:
                orders += ticket.mapped('order_ids')
        action['domain'] = [('id', 'in', orders.mapped('id'))]
        if len(orders) == 1:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = orders.id
        return action

    def action_open_so_account_move(self):
        invoices = self.mapped('sale_account_move_ids')
        if self.src_rec:
            invoices += self.src_rec.sale_account_move_ids.filtered(
                    lambda x: x.id not in invoices.mapped('id'))
            other_tickets = self.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != self.id)
            if other_tickets:
                for ticket in other_tickets:
                    invoices += ticket.sale_account_move_ids.filtered(lambda x: x.id not in invoices.mapped('id'))

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
        if self.src_rec:
            invoices += self.src_rec.sale_account_move_ids.filtered(
                    lambda x: x.id not in invoices.mapped('id'))
            other_tickets = self.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != self.id)
            if other_tickets:
                for ticket in other_tickets:
                    invoices += ticket.sale_account_move_ids.filtered(lambda x: x.id not in invoices.mapped('id'))
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
            'search_default_open': 1,
        }
        action['context'] = context
        return action

    company_currency = fields.Many2one(related="company_id.currency_id")

    @api.depends('order_ids','order_ids.invoice_ids')
    def get_sam(self):
        for record in self:
            am = []
            orders = record.order_ids
            for so in orders:
                if so.invoice_ids:
                    am.extend(so.invoice_ids.mapped('id'))
            record.sale_account_move_ids = [(6,0,am)]

    sale_account_move_ids = fields.Many2many(comodel_name='account.move', compute=get_sam, store=True)

    #@api.depends('order_ids.state', 'order_ids.currency_id', 'order_ids.amount_untaxed', 'order_ids.date_order', 'order_ids.company_id')
    def _compute_sale_data(self):
        for lead in self:
            total = 0.0
            quotation_cnt = 0
            sale_order_cnt = 0
            company_currency = lead.company_currency or self.env.company.currency_id
            orders = lead.mapped('order_ids')
            if lead.src_rec:
                orders += lead.src_rec.order_ids
                other_tickets = lead.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != self.id)
                for ticket in other_tickets:
                    orders += ticket.mapped('order_ids')
            for order in orders:
                if order.state in ('draft', 'sent'):
                    quotation_cnt += 1
                if order.state not in ('draft', 'sent', 'cancel'):
                    sale_order_cnt += 1
                    total += order.currency_id._convert(
                        order.amount_total, company_currency, order.company_id, order.date_order or fields.Date.today())
            lead.sale_amount_total = total
            lead.quotation_count = quotation_cnt
            lead.sale_order_count = sale_order_cnt

    sale_amount_total = fields.Monetary(compute='_compute_sale_data', string="Suma de ventas", help="Untaxed Total of Confirmed Orders", currency_field='company_currency')
    quotation_count = fields.Integer(compute='_compute_sale_data', string="Cantidad Presupuesto")
    sale_order_count = fields.Integer(compute='_compute_sale_data', string="Cantidad Ventas")

    def compute_sale_move_values(self):
        for record in self:
            invoice_count = 0
            invoice_total_amount = 0
            invoice_unpaid_count = 0
            invoice_unpaid_amount = 0
            sale_moves = record.mapped('sale_account_move_ids')
            if record.src_rec:
                sale_moves += record.src_rec.sale_account_move_ids.filtered(
                    lambda x: x.id not in sale_moves.mapped('id'))
                other_tickets = record.src_rec.helpdesk_ticket_ids.filtered(lambda x: x.id != record.id).filtered(
                    lambda x: x.id not in sale_moves.mapped('id'))
                if other_tickets:
                    for ticket in other_tickets:
                        sale_moves += ticket.sale_account_move_ids.filtered(lambda x: x.id not in sale_moves.mapped('id'))
            if sale_moves:
                invoice_count = len(sale_moves.filtered(lambda x: x.state == 'posted') or [])
                invoice_total_amount = sum(sale_moves.filtered(lambda x: x.state == 'posted').mapped('amount_total_signed') or [])
                invoice_unpaid_count = len(sale_moves.filtered(lambda x: x.state == 'posted' and x.amount_residual > 0) or [])
                invoice_unpaid_amount = sum(sale_moves.filtered(lambda x: x.state == 'posted' and x.amount_residual > 0).mapped('amount_residual') or [])

            record.invoice_count = invoice_count
            record.invoice_total_amount = invoice_total_amount
            record.invoice_unpaid_count = invoice_unpaid_count
            record.invoice_unpaid_amount = invoice_unpaid_amount

    invoice_count = fields.Integer(compute=compute_sale_move_values)
    invoice_total_amount = fields.Float(compute=compute_sale_move_values)
    invoice_unpaid_count = fields.Integer(compute=compute_sale_move_values)
    invoice_unpaid_amount = fields.Float(compute=compute_sale_move_values)

    def action_new_quotation(self):
        action = self.env["ir.actions.actions"]._for_xml_id("roc_custom.ticket_sale_action_quotations_new")

        opportunity_id = self.res_id if self.res_model == 'crm.lead' else False
        if not opportunity_id and self.res_model == 'sale.order':
            if self.src_rec.opportunity_id:
                opportunity_id = self.src_rec.opportunity_id.id

        action['context'] = {
            'search_default_opportunity_id': self.id,
            'default_ticket_id': self.id,
            'default_opportunity_id': opportunity_id,
            'search_default_partner_id': self.partner_id.id,
            'default_partner_id': self.partner_id.id,
            'default_campaign_id': self.campaign_id.id,
            'default_medium_id': self.medium_id.id,
            'default_origin': self.name,
            'default_source_id': self.source_id.id,
            'default_company_id': self.company_id.id or self.env.company.id,
            'default_tag_ids': [(6, 0, self.tag_ids.ids)]
        }
        if self.team_id:
            action['context']['default_team_id'] = self.team_id.id,
        if self.user_id:
            action['context']['default_user_id'] = self.user_id.id
        return action


    order_ids = fields.One2many('sale.order', 'ticket_id', string="Ordenes Venta")

    @api.depends('visit_priority')
    def compute_pr(self):
        for record in self:
            record.priority = record.visit_priority

    priority = fields.Selection(compute=compute_pr, store=True)
    partner_id = fields.Many2one('res.partner', tracking=True)

    @api.depends('partner_id', 'partner_email', 'partner_phone')
    def _compute_partner_ticket_count(self):
        def _get_email_to_search(email):
            domain = tools.email_domain_extract(email)
            return ("@" + domain) if domain and domain not in iap_tools._MAIL_DOMAIN_BLACKLIST else email

        for ticket in self:
            domain = []
            partner_ticket = ticket
            if ticket.partner_email:
                email_search = _get_email_to_search(ticket.partner_email)
                domain = expression.OR([domain, [('partner_email', 'ilike', email_search)]])
            if ticket.partner_mobile:
                domain = expression.OR([domain, [('partner_mobile', 'ilike', ticket.partner_mobile)]])
            if ticket.partner_phone:
                domain = expression.OR([domain, [('partner_phone', 'ilike', ticket.partner_phone)]])
            if ticket.partner_id:
                domain = expression.OR([domain, [("partner_id", "child_of", ticket.partner_id.commercial_partner_id.id)]])
            if domain:
                partner_ticket = self.search(domain)
            ticket.partner_ticket_ids = partner_ticket
            ticket.partner_ticket_count = len(partner_ticket - ticket._origin) if partner_ticket else 0

    partner_child_ids = fields.One2many(related='partner_id.child_ids', readonly=False)

    @api.depends('partner_id')
    def _compute_partner_mobile(self):
        for ticket in self:
            if ticket.partner_id:
                ticket.partner_mobile = ticket.partner_id.mobile

    partner_mobile = fields.Char(string='Movil', compute='_compute_partner_mobile', store=True, readonly=False, tracking=True)

    @api.depends('partner_id')
    def _compute_partner_address_fields(self):
        for record in self:
            record.partner_street = record.partner_id.street if record.partner_id else False
            record.partner_street_2 = record.partner_id.street2 if record.partner_id else False
            record.partner_city = record.partner_id.city if record.partner_id else False
            record.partner_state_id = record.partner_id.state_id if record.partner_id else False
            record.partner_zip = record.partner_id.zip if record.partner_id else False
            record.partner_country_id = record.partner_id.country_id if record.partner_id else False

    partner_street = fields.Char(string='Calle', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)
    partner_street_2 = fields.Char(string='Calle 2', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)
    partner_city = fields.Char(string='Ciudad', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)
    partner_state_id = fields.Many2one('res.country.state', string='Provincia', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)
    partner_zip = fields.Char(string='ZIP', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)
    partner_country_id = fields.Many2one('res.country', string='Pais', compute='_compute_partner_address_fields', tracking=True, store=True, readonly=False)

    assignation_config_id = fields.Many2one('helpdesk.ticket.assignator.config')
    sync_default_fields = fields.Boolean(default=True)
    partner_phone = fields.Char(tracking=True)

    @api.onchange('assignation_config_id')
    def _onchange_assignation_config_id(self):
        self.ensure_one()
        if self._origin.id:
            query = f"""
                    DELETE
                    FROM helpdesk_ticket_assignator
                    WHERE ticket_id = %s
                        """
            self._cr.execute(query, (self._origin.id,))

        if self.assignation_config_id and self.assignation_config_id.domain:
            query = self.env[self.assignation_config_id.model_id.model]._where_calc(eval(self.assignation_config_id.domain))
            from_clause, where_clause, where_clause_params = query.get_sql()
            query_txt = f"""
                INSERT INTO helpdesk_ticket_assignator
                (ticket_id, res_model, res_id, record_name, partner_id)
                SELECT %s, %s, id, {self.assignation_config_id.name_field.name}, {self.assignation_config_id.partner_field.name}
                FROM {from_clause}
                WHERE {where_clause}
            """
            self.env.cr.execute(query_txt, (self._origin.id, self.assignation_config_id.model_id.model,) + tuple(
                where_clause_params))

    @api.onchange('sync_default_fields', 'rec_selector')
    def onchange_rec_selector(self):
        self.ensure_one()
        if self.rec_selector:
            self.res_id = self.rec_selector.res_id
            self.res_model = self.rec_selector.res_model
            if self.sync_default_fields:
                self.write(self.rec_selector.src_rec.get_default_values())

    rec_selector = fields.Many2one('helpdesk.ticket.assignator', tracking=True)

    @api.depends('assignation_config_id', 'partner_id')
    def get_selector_domain(self):
        for record in self:
            if record.partner_id:
                record.selector_domain = json.dumps([('partner_id', '=', record.partner_id.id),('ticket_id', '=', record._origin.id)])
            else:
                record.selector_domain = json.dumps([('ticket_id', '=', record._origin.id)])
    selector_domain = fields.Char(compute=get_selector_domain, store=True)
    res_id = fields.Integer()
    res_model = fields.Char()

    def compute_link_to_src_doc(self):
        for record in self:
            link = """"""
            record.link_to_src_document = link

    link_to_src_document = fields.Html(compute=compute_link_to_src_doc, string="Documento Referencia")

    def get_src_doc_name(self):
        for record in self:
            if record.res_model and record.res_id:
                record.src_doc_name = record.src_rec.name
            else:
                record.src_doc_name = False

    src_doc_name = fields.Char(compute=get_src_doc_name)



    @property
    def src_rec(self):
        if self.res_model and self.res_id:
            return self.env[self.res_model].browse(self.res_id)
        else:
            return False

    def view_form_src_document(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "views": [[False, "form"]],
        }
