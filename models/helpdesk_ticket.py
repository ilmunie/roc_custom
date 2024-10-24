from odoo import fields, models, api, tools
import json
from odoo.osv import expression
from odoo.addons.iap.tools import iap_tools

class HelpDeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

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
                (ticket_id, res_model, res_id, record_name)
                SELECT %s, %s, id, {self.assignation_config_id.name_field.name}
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

    @api.depends('assignation_config_id')
    def get_selector_domain(self):
        for record in self:
            record.selector_domain = json.dumps([('ticket_id', '=', record._origin.id)])
    selector_domain = fields.Char(compute=get_selector_domain, store=True)
    res_id = fields.Integer()
    res_model = fields.Char()

    def compute_link_to_src_doc(self):
        for record in self:
            link = """"""
            record.link_to_src_document = link

    link_to_src_document = fields.Html(compute=compute_link_to_src_doc)

    def get_src_doc_name(self):
        for record in self:
            if record.res_model and record.res_id:
                record.src_doc_name = record.src_rec.name
            else:
                record.src_doc_name = False

    src_doc_name = fields.Char(compute=get_src_doc_name)



    @property
    def src_rec(self):
        return self.env[self.res_model].browse(self.res_id)

    def view_form_src_document(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": self.res_model,
            "res_id": self.res_id,
            "views": [[False, "form"]],
        }
