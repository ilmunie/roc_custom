
from odoo import fields, models, api, SUPERUSER_ID
from odoo.exceptions import UserError, ValidationError


class TechnicalJobMixin(models.AbstractModel):
    _name = 'technical.job.mixing'

    def get_sale_order(self):
        return UserError(f'No hay relacion para una Orden de venta en {self._name}')

    technical_job_type_ref = fields.Char()
    manual_technical_job = fields.Boolean(string="Publicar Aviso", tracking=True)
    manual_technical_job_request = fields.Date(string="Fecha solicitud")
    technical_job_tag_ids = fields.Many2many('technical.job.tag', string="Etiquetas", tracking=True)
    job_employee_ids = fields.Many2many('hr.employee', string="Personal Visita", tracking=True)
    job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Personal Visita", tracking=True)

    estimated_visit_revenue = fields.Float(string="Estimado (EUR)")
    job_duration = fields.Float(string="Horas estimadas")

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("update_assistant_id", False):
            self.env['technical.job.assistant'].browse(self.env.context.get("update_assistant_id", False)).related_rec_fields()
        if 'estimated_visit_revenue' in vals:
            if self.estimated_visit_revenue > 0 and self.visit_payment_type=='free':
                self.visit_payment_type = 'to_bill'
        if 'manual_technical_job' in vals:
            if self.manual_technical_job:
                self.manual_technical_job_request = fields.Date.context_today(self)
        if 'technical_job_tag_ids' in vals:
            if self.technical_schedule_job_ids:
                for job in self.technical_schedule_job_ids:
                    if job.technical_job_tag_ids.mapped('id') != self.technical_job_tag_ids.mapped('id'):
                        job.technical_job_tag_ids = [(6, 0, self.technical_job_tag_ids.mapped('id'))]
        if 'job_employee_ids' in vals:
            if self.job_employee_ids:
                for job in self.technical_schedule_job_ids:
                    if job.job_employee_ids.mapped('id') != self.job_employee_ids.mapped(
                            'id'):
                        job.job_employee_ids = [(6, 0, self.job_employee_ids.mapped('id'))]
        if 'job_vehicle_ids' in vals:
            if self.job_vehicle_ids:
                for job in self.technical_schedule_job_ids:
                    if job.job_vehicle_ids.mapped('id') != self.job_vehicle_ids.mapped(
                            'id'):
                        job.job_vehicle_ids = [(6, 0, self.job_vehicle_ids.mapped('id'))]
        if 'job_duration' in vals:
            if self.technical_schedule_job_ids:
                for job in self.technical_schedule_job_ids:
                    if job.job_duration != self.job_duration:
                        job.job_duration = self.job_duration
        if 'estimated_visit_revenue' in vals:
            if self.technical_schedule_job_ids:
                for job in self.technical_schedule_job_ids:
                    if job.estimated_visit_revenue != self.estimated_visit_revenue:
                        job.estimated_visit_revenue = self.estimated_visit_revenue
        if 'visit_payment_type' in vals:
            if self.visit_payment_type:
                for job in self.technical_schedule_job_ids:
                    if job.visit_payment_type != self.visit_payment_type:
                        job.visit_payment_type = self.visit_payment_type
        if 'visit_priority' in vals:
            if self.visit_priority:
                for job in self.technical_schedule_job_ids:
                    if job.visit_priority != self.visit_priority:
                        job.visit_priority = self.visit_priority
        if 'job_categ_ids' in vals:
            if self.technical_schedule_job_ids:
                for job in self.technical_schedule_job_ids:
                    if job.job_categ_ids.mapped('id') != self.job_categ_ids.mapped('id'):
                        job.job_categ_ids = [(6, 0, self.job_categ_ids.mapped('id'))]
        if 'visit_internal_notes' in vals:
            if self.visit_internal_notes:
                for job in self.technical_schedule_job_ids:
                    if job.internal_notes != self.visit_internal_notes:
                        job.internal_notes = self.visit_internal_notes
        return res

    @api.depends('customer_availability_type', 'customer_visit_datetime')
    def visit_job_generation(self):
        for record in self:
            model_configs = self.env['technical.job.assistant.config'].search([('model_id.model', '=', record._name)])
            config = False
            for model_conf in model_configs:
                domain = eval(model_conf.domain_condition)
                domain.insert(0, ('id', '=', record.id))
                if self.env[record._name].search_count(domain) > 0:
                    config = model_conf
                    break
            if config and record.customer_availability_type == 'specific_date' and record.customer_visit_datetime and \
                    not record.show_technical_schedule_job_ids.filtered(
                        lambda x: x.job_type_id.id == config[0].technical_job_type_id.id):
                record.write({'technical_schedule_job_ids': [(0, 0,
                                                              {'res_model': record._name,
                                                               'job_status': 'confirmed',
                                                               'res_id': record.id,
                                                               'visit_payment_type': record.visit_payment_type,
                                                               'visit_priority': record.visit_priority,
                                                               'job_categ_ids': [(6, 0, record.job_categ_ids.mapped('id'))],
                                                               'estimated_visit_revenue': record.estimated_visit_revenue,
                                                               'internal_notes': record.visit_internal_notes,
                                                               'technical_job_tag_ids': [(6, 0, record.technical_job_tag_ids.mapped('id'))],
                                                               'job_employee_ids': [(6, 0, config[
                                                                   0].technical_job_type_id.default_job_employee_ids.mapped('id'))] if not record.job_employee_ids else [(6,0,record.job_employee_ids.mapped('id'))],
                                                               'job_vehicle_ids': [(6, 0, config[
                                                                   0].technical_job_type_id.default_job_vehicle_ids.mapped('id'))] if not record.job_vehicle_ids else [(6,0,record.job_vehicle_ids.mapped('id'))],
                                                               'job_type_id': config[
                                                                   0].technical_job_type_id.id,
                                                               'job_duration': record.job_duration if record.job_duration>0 else config[
                                                                   0].technical_job_type_id.default_duration_hs,
                                                               'user_id': config[
                                                                   0].responsible_user_id.id,
                                                               'date_schedule': record.customer_visit_datetime})]})
            record.trigger_visit_job_generation = True if record.trigger_visit_job_generation else False



    trigger_visit_job_generation = fields.Boolean(store=True, compute=visit_job_generation)
    visit_payment_type = fields.Selection(string="Política de cobro", selection=[('free','Sin cargo'), ('to_bill','Con cargo')])
    visit_priority = fields.Selection(string="Prioridad Visita", selection=[('0', 'Sin definir'), ('1','Baja'), ('2','Media'), ('3','Alta')])
    job_categ_ids = fields.Many2many('technical.job.categ', string="Categoria")
    customer_availability_type = fields.Selection(string="Tipo disponibilidad",
                                                  selection=[('no_data', 'Sin información'),
                                                             ('specific_date', 'Coordinación exacta'),
                                                             ('hour_range', 'Franja horaria'),
                                                             ('week_availability', 'Disponibilidad semanal'),
                                                             ('urgent', 'Urgente')],
                                                  default='no_data')

    customer_visit_datetime = fields.Datetime(string="Horario coordinado")
    customer_av_visit_date = fields.Date(string="Fecha coordinada")
    customer_av_hour_start = fields.Selection(string="Hora inicio", selection=[('07', '07'), ('08', '08'), ('09', '09'), ('10', '10'),
                                                         ('11', '11'), ('12', '12'), ('13', '13'), ('14', '14'),
                                                         ('15', '15'), ('16', '16'), ('17', '17'), ('18', '18')], default="08")
    customer_av_min_start = fields.Selection(string="Min inicio", selection=[('00', '00'), ('15', '15'), ('30', '30'), ('45', '45')], default="00")
    customer_av_hour_end = fields.Selection(string="Hora fin", selection=[('07', '07'), ('08', '08'), ('09', '09'), ('10', '10'),
                                                         ('11', '11'), ('12', '12'), ('13', '13'), ('14', '14'),
                                                         ('15', '15'), ('16', '16'), ('17', '17'), ('18', '18')], default="08")
    customer_av_min_end = fields.Selection(string="Min fin", selection=[('00', '00'), ('15', '15'), ('30', '30'), ('45', '45')], default="00")
    customer_availability_info = fields.Text(string="Disponibilidad cliente")
    customer_availability_widget_data = fields.Char(string="Disponibilidad cliente (Widget)")
    priority_type_widget_data = fields.Char(string="Prioridad (Widget)")

    visit_internal_notes = fields.Text(string="Nota a técnico")

    @api.onchange('customer_availability_type', 'customer_visit_datetime', 'customer_av_visit_date',
                  'customer_av_hour_start', 'customer_av_min_start', 'customer_av_hour_end', 'customer_av_min_end')
    def _compute_customer_availability_info(self):
        for record in self:
            availability_text = ""
            if record.customer_availability_type == 'no_data':
                availability_text = "Sin información"
            elif record.customer_availability_type == 'specific_date':
                if record.customer_visit_datetime:
                    availability_text = f"Coordinación exacta: {record.customer_visit_datetime}"
                else:
                    availability_text = "Coordinación exacta: Fecha y hora no especificadas"
            elif record.customer_availability_type == 'hour_range':
                availability_text = f"Franja horaria:"
                if record.customer_av_visit_date:
                    availability_text += f" día {record.customer_av_visit_date}"
                if record.customer_av_hour_start and record.customer_av_min_start and record.customer_av_hour_end and record.customer_av_min_end:
                    availability_text += f" de {record.customer_av_hour_start}:{record.customer_av_min_start}"
                    availability_text += f" a {record.customer_av_hour_end}:{record.customer_av_min_end}"
            elif record.customer_availability_type == 'week_availability':
                availability_text = "Disponibilidad semanal: Por definir"
            elif record.customer_availability_type == 'urgent':
                availability_text = "A VISITAR URGENTE"

            record.customer_availability_info = availability_text

    def get_job_data(self):
        return False

    technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', order='date_schedule DESC', copy=False)
    @api.depends('technical_schedule_job_ids','technical_schedule_job_ids.date_schedule')
    def show_technical_jobs(self):
        for record in self:
            record.show_technical_schedule_job_ids = [(6,0,record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule).mapped('id'))]

    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=show_technical_jobs, string="Trabajos técnicos", order='date_schedule DESC')

    @api.depends('technical_schedule_job_ids', 'technical_schedule_job_ids.minutes_in_job')
    def compute_total_job_minutes(self):
        for record in self:
            minutes = record.technical_schedule_job_ids.filtered(lambda x: x.minutes_in_job).mapped('minutes_in_job')
            record.total_job_minutes = sum(minutes) if minutes else 0
    total_job_minutes = fields.Float(string="Min. registrados", compute="compute_total_job_minutes", store=True)
    def get_qty_technical_jobs(self):
        for record in self:
            qty = 0
            qty_active = 0
            if record.technical_schedule_job_ids:
                qty = int(len(record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule).mapped('id')))
                qty_active = int(len(record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule and x.job_status not in ['cancel', 'done']).mapped('id')))
            record.technical_job_count = qty
            record.active_technical_job_count = qty_active

    technical_job_count = fields.Float(compute=get_qty_technical_jobs)
    active_technical_job_count = fields.Float(compute=get_qty_technical_jobs)
    @api.depends('technical_schedule_job_ids','technical_schedule_job_ids.job_status','technical_schedule_job_ids.date_schedule','technical_schedule_job_ids.job_employee_ids','technical_schedule_job_ids.job_vehicle_ids')
    def get_next_job(self):
        for record in self:
            res = False
            next_active_job_date = False
            active_jobs = sorted(record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule and x.job_status not in ('done', 'cancel')), key=lambda x: x.date_schedule)
            if active_jobs:
                res = active_jobs[0].id
                next_active_job_date = active_jobs[0].date_schedule
            record.next_active_job_id = res
            record.next_active_job_date = next_active_job_date
            tjas = self.env['technical.job.assistant'].search([('create_uid','=',self.env.user.id), ('res_id','=',record.id), ('res_model','=',record._name)])
            for tja in tjas:
                tja.related_rec_fields()

    next_active_job_id = fields.Many2one('technical.job.schedule', compute=get_next_job, store=True, string= "Próx. Planificación",)
    next_active_job_date = fields.Datetime(compute=get_next_job, store=True, tracking=True, string="Fecha Proxima operacion")

    def open_next_job_calendar_view(self):
        self.ensure_one()
        if self.next_active_job_id:
            action = self.next_active_job_id.open_in_calendar_view()
            return action

    def action_schedule_job(self):
        self.ensure_one()
        configs = self.env['technical.job.assistant.config'].search([('model_name','=',self._name)])
        job_type_id = False
        for config in configs:
            domain = eval(config.domain_condition)
            domain.insert(0, ('id', '=', self.id))
            if self.env[self._name].search(domain):
                job_type_id = config.technical_job_type_id.id if config.technical_job_type_id else False
                break
        action = self.sudo().env["ir.actions.actions"]._for_xml_id("roc_custom.action_technical_job")
        self.write({'technical_schedule_job_ids': [(0, 0, {'res_model': self._name, 'res_id': self.id})]})
        action['name'] = 'Nueva operación ' + self.display_name

        action['context'] = {
            'default_schedule_id': self.technical_schedule_job_ids.filtered(lambda x: not x.date_schedule)[0].id,
            'default_res_id': self.id,
            'default_job_type_id': job_type_id,
            'search_default_active': 1,
            'default_res_model': self._name,
            'default_user_id': self.env.user.id,
            'default_mode': "week" if self.env.user.has_group('roc_custom.technical_job_planner') else "day",
            'initial_date': False,
        }
        #import pdb;pdb.set_trace()
        return action



class CrmLead(models.Model,TechnicalJobMixin):
    _inherit = 'crm.lead'

    @api.depends('customer_availability_type', 'customer_visit_datetime', 'stage_id')
    def visit_job_generation(self):
        return super().visit_job_generation()
    trigger_visit_job_generation = fields.Boolean(store=True, compute=visit_job_generation)

    def get_sale_order(self):
        #sales = self.order_ids.filtered(lambda x: x.state not in ('cancel') and x.invoice_status != 'invoiced')
        #return sales[0] if sales else False
        return False
    @api.depends('expected_revenue')
    def sync_exp_rev(self):
        for record in self:
            if record.expected_revenue and record.expected_revenue != record.estimated_visit_revenue:
                record.estimated_visit_revenue = record.expected_revenue
            record.trigger_sync_expected_revenue = False if record.trigger_sync_expected_revenue else True
    trigger_sync_expected_revenue = fields.Boolean(compute=sync_exp_rev, store=True )

    def get_job_data(self):
        data = ''
        if self.customer_availability_type == 'urgent':
            data += "<strong>" + dict(self._fields['customer_availability_type']._description_selection(self.env)).get(self.customer_availability_type) + "<strong/><br/><br/>"
        if self.type_of_client:
            data += "Tipo de cliente: " + dict(self._fields['type_of_client']._description_selection(self.env)).get(self.type_of_client) + "<br/><br/>"
        if self.mobile or self.mobile_partner or self.phone:
            phone_number = self.mobile or self.mobile_partner or self.phone
            data += f"""
                <a href='tel:{phone_number.replace(" ","").replace("-","")}'><br/>
                   📲 Llamar Cliente<br/><br/>
                </a>
                <a href='https://wa.me/{phone_number.replace(" ","").replace("-","")}'><br/>
                   💬 Enviar WhatsApp {phone_number.replace(" ","").replace("-","")}<br/><br/>
                </a>
            """

        if self.address_label:
            data += f"<a href='https://google.com/maps/search/{self.address_label}'><br/>📍 Dirección: {self.address_label}<br/><br/></a>"
        if self.customer_availability_info:
            data += self.customer_availability_info + "<br/><br/>"

        if self.work_type_id:
            data += f"Tipo de obra: {self.work_type_id.name}<br/><br/>"

        if self.intrest_tag_ids:
            data += f"Intereses: {' | '.join(self.intrest_tag_ids.mapped('name'))}<br/><br/>"

        if self.description:
            if "Se le informó / respondió:" in self.description:
                position = self.description.find("Se le informó / respondió:")
                # If the phrase is found, extract the content before it
                data += f"{self.description[:position].strip()}<br/><br/>"
            else:
                data += f"{self.description}<br/><br/>"

        if self.partner_id and self.partner_id.child_ids:
            data += f"<br/><bold><span>CONTACTOS ALTERNATIVOS: <span/><bold/>"
            for child_contact in self.partner_id.child_ids:
                phone_number = child_contact.mobile or child_contact.phone
                if phone_number:
                    data += f"""
                        <a href='tel:{phone_number.replace(" ", "").replace("-", "")}'><br/>
                           📲 Llamar {child_contact.name}<br/><br/>
                        </a>
                        <a href='https://wa.me/{phone_number.replace(" ", "").replace("-", "")}'><br/>
                           💬 Enviar WhatsApp {phone_number.replace(" ", "").replace("-", "")}<br/><br/>
                        </a>
                    """
        return data

    address_label = fields.Char(
        string='Direccion',
        compute='_compute_address_label',
    )

    @api.depends('street', 'street2', 'city', 'zip', 'state_id')
    def _compute_address_label(self):
        for lead in self:
            address = False
            if lead.street or lead.street2 :
                address_components = [lead.street,lead.street2, lead.city, lead.zip, "España"]
                if lead.state_id:
                    address_components.append(lead.state_id.name)
                address = ', '.join(filter(None, address_components))
            if not address:
                address = "Sin datos de dirección"
            lead.address_label = address

class StockPicking(models.Model,TechnicalJobMixin):
    _inherit = 'stock.picking'

    def get_job_data(self):
        return self.address_label

    address_label = fields.Char(
        string='Direccion',
        compute='_compute_address_label',
    )

    @api.depends('partner_id','partner_id.street','partner_id.street2','partner_id.city','partner_id.zip')
    def _compute_address_label(self):
        for picking in self:
            address = ''
            partner = picking.partner_id
            if partner:
                address_components = [partner.street, partner.street2, partner.city, partner.zip]
                if partner.state_id:
                    address_components.append(partner.state_id.name)
                address = ', '.join(filter(None, address_components))
                if not address:
                    address = "Sin datos de dirección"
            picking.address_label = address


class PurchaseOrder(models.Model,TechnicalJobMixin):
    _inherit = 'purchase.order'

    def get_job_data(self):
        return self.address_label

    address_label = fields.Char(
        string='Direccion',
        compute='_compute_address_label',
    )

    @api.depends('partner_id','partner_id.street','partner_id.street2','partner_id.city','partner_id.zip')
    def _compute_address_label(self):
        for order in self:
            address = ''
            partner = order.partner_id
            if partner:
                address_components = [partner.street, partner.street2, partner.city, partner.zip]
                if partner.state_id:
                    address_components.append(partner.state_id.name)
                address = ', '.join(filter(None, address_components))
                if not address:
                    address = "Sin datos de dirección"
            order.address_label = address

class SaleOrder(models.Model,TechnicalJobMixin):
    _inherit = 'sale.order'

    #technical_job_schedule_ids = fields.One2many('technical.job.schedule', 'sale_order_id')

    def get_job_data(self):
        return self.address_label

    address_label = fields.Char(
        string='Direccion',
        compute='_compute_address_label',
    )

    @api.depends('partner_id','partner_id.street','partner_id.street2','partner_id.city','partner_id.zip')
    def _compute_address_label(self):
        for order in self:
            address = ''
            partner = order.partner_shipping_id
            if partner:
                address_components = [partner.street, partner.street2, partner.city, partner.zip]
                if partner.state_id:
                    address_components.append(partner.state_id.name)
                address = ', '.join(filter(None, address_components))
                if not address:
                    address = "Sin datos de dirección"
            order.address_label = address

class MrpProduction(models.Model,TechnicalJobMixin):
    _inherit = 'mrp.production'



class HelpdeskTicket(models.Model,TechnicalJobMixin):
    _inherit = 'helpdesk.ticket'



    def get_job_data(self):
        data = ''
        if self.customer_availability_type == 'urgent':
            data += "<strong>" + dict(self._fields['customer_availability_type']._description_selection(self.env)).get(self.customer_availability_type) + "<strong/><br/><br/>"
        if self.partner_mobile or self.partner_phone:
            phone_number = self.partner_mobile or self.partner_phone
            data += f"""
                <a href='tel:{phone_number.replace(" ","").replace("-","")}'><br/>
                   📲 Llamar Cliente<br/><br/>
                </a>
                <a href='https://wa.me/{phone_number.replace(" ","").replace("-","")}'><br/>
                   💬 Enviar WhatsApp {phone_number.replace(" ","").replace("-","")}<br/><br/>
                </a>
            """
        if self.address_label:
            data += f"<a href='https://google.com/maps/search/{self.address_label}'><br/>📍 Dirección: {self.address_label}<br/><br/></a>"
        if self.customer_availability_info:
            data += self.customer_availability_info + "<br/><br/>"

        if self.description:
            if "Se le informó / respondió:" in self.description:
                position = self.description.find("Se le informó / respondió:")
                # If the phrase is found, extract the content before it
                data += f"{self.description[:position].strip()}<br/><br/>"
            else:
                data += f"{self.description}<br/><br/>"

        if self.partner_id and self.partner_id.child_ids:
            data += f"<br/><bold><span>CONTACTOS ALTERNATIVOS: <span/><bold/>"
            for child_contact in self.partner_id.child_ids:
                phone_number = child_contact.mobile or child_contact.phone
                if phone_number:
                    data += f"""
                        <a href='tel:{phone_number.replace(" ", "").replace("-", "")}'><br/>
                           📲 Llamar {child_contact.name}<br/><br/>
                        </a>
                        <a href='https://wa.me/{phone_number.replace(" ", "").replace("-", "")}'><br/>
                           💬 Enviar WhatsApp {phone_number.replace(" ", "").replace("-", "")}<br/><br/>
                        </a>
                    """
        return data

    address_label = fields.Char(
        string='Direccion',
        compute='_compute_address_label',
    )

    @api.depends('partner_street', 'partner_street_2', 'partner_city', 'partner_zip', 'partner_state_id')
    def _compute_address_label(self):
        for lead in self:
            address = False
            if lead.partner_street or lead.partner_street_2 :
                address_components = [lead.partner_street,lead.partner_street_2, lead.partner_city, lead.partner_zip, "España"]
                if lead.partner_state_id:
                    address_components.append(lead.partner_state_id.name)
                address = ', '.join(filter(None, address_components))
            if not address:
                address = "Sin datos de dirección"
            lead.address_label = address