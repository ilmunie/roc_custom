from odoo import fields, models, api, tools
import json



class HelpDeskTicketAssignatorConfig(models.Model):
    _name = 'helpdesk.ticket.assignator.config'

    name = fields.Char()
    model_id = fields.Many2one('ir.model')
    domain = fields.Char()
    name_field = fields.Many2one('ir.model.fields')

    @api.depends('model_id')
    def get_domain(self):
        for record in self:
            res = [('id', '=', 0)]
            if record.model_id:
                res = [('model_id', '=', record.model_id.id), ('store','=', True)]
            record.field_domain = json.dumps(res)
    field_domain = fields.Char(compute=get_domain, store=True)
    model_name = fields.Char(related='model_id.model')


class HelpDeskTicketAssignator(models.Model):
    _name = 'helpdesk.ticket.assignator'



    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += [('record_name', 'ilike', name)]
            name = ''
        return super(HelpDeskTicketAssignator, self).name_search(name=name, args=args, operator=operator, limit=limit)

    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, record.record_name))
        return res


    record_name = fields.Char()
    res_id = fields.Integer()
    res_model = fields.Char()
    ticket_id = fields.Many2one('helpdesk.ticket', ondelete='cascade')

    @property
    def src_rec(self):
        return self.env[self.res_model].browse(self.res_id)

class HelpDeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    active_process = fields.Boolean()


class HelpDeskMixin(models.AbstractModel):
    _name = 'help.desk.mixing'


    def get_tickets(self):
        for record in self:
            tickets = self.env['helpdesk.ticket'].search([('res_model','=', record._name),
                                                  ('res_id', '=', record._origin.id)]).mapped('id')
            record.helpdesk_ticket_ids = [(6,0,tickets)]
    helpdesk_ticket_ids = fields.Many2many('helpdesk.ticket', compute=get_tickets)

    def get_default_values(self):
        vals_to_ticket = {
            'res_id': self.id,
            'res_model': self._name
        }
        if 'trigger_visit_job_generation' in self._fields.keys():
            vals_to_ticket['manual_technical_job'] = self.manual_technical_job
            vals_to_ticket['manual_technical_job_request'] = self.manual_technical_job_request
            vals_to_ticket['technical_job_tag_ids'] = [(6, 0,self.technical_job_tag_ids.mapped('id'))]
            vals_to_ticket['job_employee_ids'] = [(6, 0,self.job_employee_ids.mapped('id'))]
            vals_to_ticket['job_vehicle_ids'] = [(6, 0,self.job_vehicle_ids.mapped('id'))]
            vals_to_ticket['technical_job_type_ref'] = self.technical_job_type_ref
            vals_to_ticket['estimated_visit_revenue'] = self.estimated_visit_revenue
            vals_to_ticket['job_duration'] = self.job_duration
            vals_to_ticket['visit_payment_type'] = self.visit_payment_type
            vals_to_ticket['visit_priority'] = self.visit_priority
            vals_to_ticket['job_categ_ids'] = [(6, 0,self.job_categ_ids.mapped('id'))]
            vals_to_ticket['customer_availability_type'] = self.customer_availability_type
            vals_to_ticket['customer_visit_datetime'] = self.customer_visit_datetime
            vals_to_ticket['customer_av_visit_date'] = self.customer_av_visit_date
            vals_to_ticket['customer_av_hour_start'] = self.customer_av_hour_start
            vals_to_ticket['customer_av_min_start'] = self.customer_av_min_start
            vals_to_ticket['customer_av_hour_end'] = self.customer_av_hour_end
            vals_to_ticket['customer_av_min_end'] = self.customer_av_min_end
            vals_to_ticket['customer_availability_info'] = self.customer_availability_info
            vals_to_ticket['visit_internal_notes'] = self.visit_internal_notes
        return vals_to_ticket

    @api.depends('helpdesk_ticket_ids', 'helpdesk_ticket_ids.stage_id', 'helpdesk_ticket_ids.stage_id.active_process')
    def compute_active_ticket_count(self):
        for record in self:
            record.active_ticket_count = len(record.helpdesk_ticket_ids.filtered(lambda x: x.stage_id.active_process))

    active_ticket_count = fields.Integer(compute=compute_active_ticket_count)

    def view_tickets(self):
        ctx = self.get_default_values()
        action = {
            "name": "Tickets",
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "context": ctx,
            "view_mode": 'tree',
            'view_ids': [(False, 'list'), (False, 'form')],
            "domain": [('res_id', '=', self.id),('res_model', '=', self._name)]
        }
        return action

    def create_new_ticket(self):
        ctx = self.get_default_values()
        final_ctx = {}
        for key, value in ctx.items():
            final_ctx['default_' + key] = value
        action = {
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "context": final_ctx,
            'view_mode': 'form',
        }
        return action


class SaleOrder(models.Model,HelpDeskMixin):
    _inherit = 'sale.order'


    def get_default_values(self):
        res = {}
        res.update(super(SaleOrder, self).get_default_values())
        if self.opportunity_id:
            opp_data = self.opportunity_id.get_default_values()
            opp_data.pop('res_id')
            opp_data.pop('res_model')
            res.update(opp_data)
        if self.partner_shipping_id:
            res['partner_id'] = self.partner_shipping_id.id
        return res


    @api.depends('name', 'partner_id', 'trigger_compute_assignation_name', 'opportunity_id')
    def compute_ticket_assignation_name(self):
        for record in self:
            name = ""
            if record.opportunity_id:
                name = "[" + record.opportunity_id.name + "] "
            if record.name:
                name += record.name
            if record.partner_id:
                    name += " - " + record.partner_id.name
            record.ticket_assignation_name = name

    ticket_assignation_name = fields.Char(compute=compute_ticket_assignation_name, store=True)
    trigger_compute_assignation_name = fields.Boolean()


class CrmLead(models.Model,HelpDeskMixin):
    _inherit = 'crm.lead'


    def get_default_values(self):
        res = super(CrmLead, self).get_default_values()
        if self.partner_id:
            res['partner_id'] = self.partner_id.id
        res['name'] = "TICKET -" + self.name
        return res

    @api.depends('name', 'partner_id', 'trigger_compute_assignation_name')
    def compute_ticket_assignation_name(self):
        for record in self:
            name = ""
            if record.name:
                name += record.name
            if record.partner_id:
                    name += " - " + record.partner_id.name
            record.ticket_assignation_name = name

    ticket_assignation_name = fields.Char(compute=compute_ticket_assignation_name, store=True)
    trigger_compute_assignation_name = fields.Boolean()