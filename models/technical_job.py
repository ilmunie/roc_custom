from odoo import fields, models, api, SUPERUSER_ID
from datetime import timedelta, datetime
import pytz
from odoo.tools.misc import DEFAULT_SERVER_DATETIME_FORMAT

class TechnicalJobType(models.Model):
    _name = 'technical.job.type'

    name = fields.Char(string="Name")
    default_duration_hs = fields.Float(string="Duración Hs")
    default_job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita", domain=[('technical','=',True)])
    default_job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")



class TechnicalJobSchedule(models.Model):
    _name = 'technical.job.schedule'
    order = 'date_schedule DESC'

    def stop_tracking(self):
        self.ensure_one()
        time_difference = fields.Datetime.now() - self.start_tracking_time
        self.minutes_in_job += time_difference.total_seconds() / 60
        self.start_tracking_time = False

    def start_tracking(self):
        self.ensure_one()
        self.start_tracking_time = fields.Datetime.now()

    minutes_in_job = fields.Float(string="Minutos trabajados")
    start_tracking_time = fields.Datetime()

    def get_job_time_str(self):
        """
        Generate a string representing the job's start date, start time, and end time in the user's timezone.
        :return: A string in the format 'start date HH:mm(start-time) - HH:mm(end-time)'.
        """
        if not self.date_schedule:
            return ""

        # Get the user's timezone
        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        # Convert the date_schedule to a datetime object in UTC
        start_datetime_utc = fields.Datetime.from_string(self.date_schedule)

        # Convert the start time to the user's timezone
        start_datetime = start_datetime_utc.astimezone(local_tz)

        # Calculate the end time
        end_datetime = start_datetime + timedelta(hours=self.job_duration)

        # Format the start and end times
        start_time_str = start_datetime.strftime("%H:%M")
        end_time_str = end_datetime.strftime("%H:%M")
        date_str = start_datetime.strftime("%d/%m/%y")

        return f"{date_str} {start_time_str} - {end_time_str}"

    @api.depends('job_status', 'date_schedule', 'job_employee_ids', 'job_vehicle_ids', 'job_duration')
    def warning_full_calendar(self):
        #import pdb;pdb.set_trace()
        wrn_msg_emp = ''
        wrn_msg_vh = ''
        employee_not = []
        vehicle_not = []
        for record in self:
            if record.job_status in ('done', 'cancel'):
                record.trigger_warning_full_calendar = False
                continue
            start_time = record.date_schedule
            end_time = start_time + timedelta(hours=record.job_duration) if start_time else start_time
            for employee_id in record.job_employee_ids:
            # Check for overlaps with employee's calendar
                if employee_id and record.date_schedule:
                    overlapping_jobs_employee = self.env['technical.job'].search([
                        ('schedule_id', '!=', record.id),
                        ('job_employee_id', '=', employee_id.id),
                        ('date_schedule', '<=', end_time),
                        ('job_status', 'in', ('confirmed', 'to_do', 'stand_by')),
                        ('end_time', '>=', record.date_schedule)
                    ])
                    if overlapping_jobs_employee and employee_id.id not in employee_not:
                        wrn_msg_emp += f"{employee_id.name} | Agenda ocupada {overlapping_jobs_employee[0].schedule_id.get_job_time_str()}  ----  "
                        employee_not.append(employee_id.id)
                    # Check for overlaps with vehicle's calendar
            for job_vehicle_id in record.job_vehicle_ids:
                if job_vehicle_id and record.date_schedule:
                    overlapping_jobs_vehicle = self.env['technical.job'].search([
                        ('id', '!=', record.id),
                        ('schedule_id', '!=', record.id),
                        ('job_vehicle_id', '=', job_vehicle_id.id),
                        ('date_schedule', '<=', end_time),
                        ('job_status', 'in', ('confirmed', 'to_do', 'stand_by')),
                        ('end_time', '>=', record.date_schedule)])
                    if overlapping_jobs_vehicle and job_vehicle_id.id not in vehicle_not:
                        wrn_msg_vh += f"{job_vehicle_id.name} | Agenda ocupada {overlapping_jobs_vehicle[0].schedule_id.get_job_time_str()}  ----  "
                        vehicle_not.append(job_vehicle_id.id)
                    # Set the warning flag
            record.trigger_warning_full_calendar = bool(wrn_msg_emp) or bool(wrn_msg_vh)
                # Optionally, you could store or log the warning message somewhere if needed
        if wrn_msg_emp:
            self.env.user.notify_warning(message=wrn_msg_emp, sticky=True)
        if wrn_msg_vh:
            self.env.user.notify_warning(message=wrn_msg_vh, sticky=True)

    trigger_warning_full_calendar = fields.Boolean(compute=warning_full_calendar, store=True)


    def open_form_view(self):
        action = self.env.ref('roc_custom.action_technical_job_form').read()[0]
        action["res_id"] = self.id
        return action

    def open_in_calendar_view(self):
        action = self.env.ref('roc_custom.action_technical_job').read()[0]
        action['context'] = {
                'default_mode': 'week' if self.env.user.has_group('roc_custom.technical_job_planner') else 'day',
                'initial_date': self.date_schedule,
                'search_default_res_model': self.res_model,
                'search_default_res_id': self.res_id,
        }
        return action

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            name = ''
            if rec.source_document_display_name:
                name = rec.source_document_display_name
            if rec.job_type_id:
                if name:
                    name += " | "
                name += rec.job_type_id.name
            if rec.job_employee_ids:
                if name:
                    name += " | "
                    name += " | "
                name += ','.join(rec.job_employee_ids.mapped('name'))
            if rec.job_vehicle_ids:
                if name:
                    name += " | "
                name += ','.join(rec.job_vehicle_ids.mapped('name'))
            res.append((rec.id, name))
        return res
    def get_data_src_doc(self):
        for record in self:
            html = '<table>'
            if record.res_id and record.res_model:
                rec = self.env[record.res_model].browse(record.res_id)
                if rec:
                    info = rec.get_job_data()
                    if info:
                        html += info
            html += '</table>'
            record.html_data_src_doc = html
    html_data_src_doc = fields.Html(compute=get_data_src_doc, string="Info")




    @api.depends('res_model', 'res_id')
    def get_html_link_to_src_doc(self):
        for record in self:
            html = ""
            html += "<table style='border-collapse: collapse; border: none;'>"
            html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(
                record.res_id,
                record.res_model)
            html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(record.source_document_display_name)
            record.html_link_to_src_doc = html

    html_link_to_src_doc = fields.Html(compute=get_html_link_to_src_doc, string="Doc. Origen", store=True)
    @api.depends('res_id','res_model')
    def get_source_doc_name(self):
        for record in self:
            name = ''
            if record.res_id and record.res_model:
                rec = self.env[record.res_model].browse(record.res_id)
                if rec:
                    name = rec.display_name
            record.source_document_display_name = name
    source_document_display_name = fields.Char(compute=get_source_doc_name, string="Documento origen", store=True)


    job_type_id = fields.Many2one('technical.job.type', string="Tipo trabajo")
    res_model = fields.Char()
    res_id = fields.Integer()
    job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita", domain=[('technical','=',True)])
    job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")
    date_schedule = fields.Datetime(string="Fecha a visitar")
    user_id = fields.Many2one('res.users', store=True, string="Responsable")
    job_duration = fields.Float(string="Tiempo trabajo (hs.)")
    job_status = fields.Selection(
        selection=[('to_do', 'Planificado'), ('confirmed', 'Confirmado'), ('stand_by', 'Aplazado'), ('done', 'Terminado'), ('cancel', 'Cancelado')],
        string="Estado", default='to_do')
    internal_notes = fields.Text(string="Notas internas")
    attch_ids = fields.Many2many('ir.attachment', 'ir_attach_rel', 'technical_job', 'attachment_id',
                                 string="Adjuntos",
                                 help="If any")


    real_rec_message_id = fields.Many2one('mail.message')
    @api.depends('job_status')
    def compute_last_date_status(self):
        for record in self:
            record.date_status = fields.Datetime.now()

    date_status = fields.Datetime(string="Cambio estado", compute=compute_last_date_status, store=True)


    trigger_refresh_jobs = fields.Boolean(compute='refresh_jobs', store=True)



    @api.depends('job_employee_ids', 'job_vehicle_ids')
    def refresh_jobs(self):
        for rec in self:
            jobs_to_delete = self.env['technical.job'].search([('schedule_id', '=', rec.id)])
            for job in jobs_to_delete:
                job.active = False
            if rec.job_employee_ids:
                for employee in rec.job_employee_ids:
                    if rec.job_vehicle_ids:
                        for vehicle in rec.job_vehicle_ids:
                            self.env['technical.job'].create({
                                'job_employee_id': employee.id,
                                'job_vehicle_id': vehicle.id,
                                'schedule_id': rec.id
                                                    })
                    else:
                        self.env['technical.job'].create({
                            'job_employee_id': employee.id,
                            'job_vehicle_id': False,
                            'schedule_id': rec.id
                        })
            else:
                if rec.job_vehicle_ids:
                    for vehicle in rec.job_vehicle_ids:
                        self.env['technical.job'].create({
                            'job_employee_id': False,
                            'job_vehicle_id': vehicle.id,
                            'schedule_id': rec.id
                        })
                else:
                    self.env['technical.job'].create({
                        'job_employee_id': False,
                        'job_vehicle_id': False,
                        'schedule_id': rec.id
                    })

            rec.trigger_refresh_jobs = False if rec.trigger_refresh_jobs else False


class TechnicalJob(models.Model):
    _name = 'technical.job'

    def menu_to_calendar(self):
        action = self.env.ref('roc_custom.action_technical_job').read()[0]
        user_type = 'planner' if self.env.user.has_group('roc_custom.technical_job_planner') else 'user'
        if user_type == 'user':
            context = {
                'search_default_myjobs': 1,
                'default_mode': "week" if self.env.user.has_group('roc_custom.technical_job_planner') else "day"}
            action['context'] = context
        return action
    #

    @api.onchange('job_type_id')
    def _onchange_job_type_id(self):
        for record in self:
            if record.job_type_id.default_job_employee_ids:
                record.job_employee_ids = [(6, 0, record.job_type_id.default_job_employee_ids.mapped('id'))]
            if record.job_type_id.default_job_vehicle_ids:
                record.job_vehicle_ids = [(6, 0, record.job_type_id.default_job_vehicle_ids.mapped('id'))]
            if record.job_type_id.default_duration_hs:
                record.job_duration = record.job_type_id.default_duration_hs

    @api.model_create_multi
    def create(self, vals_list):
        new_vals = []
        for vals in vals_list:
            if 'schedule_id' in vals.keys() and not vals.get('schedule_id', False):
                vals.pop('schedule_id')
                vals['schedule_id'] = self.env['technical.job.schedule'].create(vals).id
                new_vals.append(vals)
            else:
                new_vals.append(vals)
        records = super().create(new_vals)
        return records
    def confirm(self):
        for record in self:
            jobs_edit = []
            jobs_edit.append(record)
            if record.schedule_id:
                jobs_edit.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_edit:
                job.write({'job_status': 'confirmed'})
    def stand_by(self):
        for record in self:
            jobs_edit = []
            jobs_edit.append(record)
            if record.schedule_id:
                jobs_edit.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_edit:
                job.write({'job_status': 'stand_by'})
    def set_draft(self):
        for record in self:
            jobs_edit = []
            jobs_edit.append(record)
            if record.schedule_id:
                jobs_edit.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_edit:
                job.write({'job_status': 'to_do'})

    def mark_as_done(self):
        for record in self:
            jobs_to_make_done = []
            jobs_to_make_done.append(record)
            if record.schedule_id:
                jobs_to_make_done.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_to_make_done:
                job.write({'job_status': 'done'})

            #generic implementation comment and attachments
            schedule_id = record.schedule_id
            if schedule_id.attch_ids or schedule_id.internal_notes and (record.res_id and record.res_model):
                rec = self.env[record.res_model].browse(record.res_id)
                body = schedule_id.internal_notes or ''
                if schedule_id.attch_ids:
                    if body:
                        body += "<br/>"
                    body += "Ha modificado los archivos adjuntos"
                rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment', attachment_ids=schedule_id.attch_ids.mapped('id'))
            if (record.res_id and record.res_model):
                body = "Ha finalizado la operación: " + record.job_type_id.name
                if record.minutes_in_job:
                    body += f"<br/> TIEMPO TOTAL REGISTRADO: {round(record.minutes_in_job, 0)} min"
                rec = self.env[record.res_model].browse(record.res_id)
                rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment',
                                                                            partner_ids=rec.user_id.mapped(
                                                                                'partner_id.id'))
            #custom implementation for crm lead mark as done
            if (record.res_id and record.res_model and record.res_model == 'crm.lead'):
                rec = self.env[record.res_model].browse(record.res_id)
                if rec.stage_id.name == 'Visita':
                    stages = self.env['crm.stage'].search([('name', '=', 'Procesamiento Roconsa')])
                    if not stages:
                        raise ValueError('No hay etapa de crm llamada Procesamiento Roconsa')
                    else:
                        rec.stage_id = stages[0].id
                assistant_to_delete = self.env['technical.job.assistant'].search([('res_model', '=', record.res_model), ('res_id', '=', record.res_id)])
                assistant_to_delete.unlink()
                if self.env.context.get("from_kanban", False):
                    ctx = self.env.context.copy()
                    ctx.pop('from_kanban')
                    return {
                        'name': "Planificación de Operaciones",
                        'res_model': 'technical.job.assistant',
                        'type': 'ir.actions.act_window',
                        'context': ctx,
                        'domain': [('create_uid', '=', self.env.user.id)],
                        'views': [(False, 'kanban'), (self.env.ref('roc_custom.technical_job_assistant_tree_view').id, 'tree')],
                    }



    def delete_schedule_tree(self):
        deleted_ids = []
        for record in self:
            if record.id not in deleted_ids:
                if record.schedule_id:
                    deleted_ids.extend(self.env['technical.job'].search([('schedule_id','=',record.schedule_id.id)]).mapped('id'))
                    record.schedule_id.unlink()
                else:
                    record.unlink()

    def delete_schedule(self):
        for record in self:
            action = self.schedule_id.open_in_calendar_view()
            action.pop('context')
            if record.schedule_id:
                record.schedule_id.unlink()
            else:
                record.unlink()
            return action

    def clean_technical_job(self):
        self.env['technical.job'].search([('active','=',False)]).unlink()
        return

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            name = ''
            if rec.job_status:
                name += dict(rec._fields['job_status']._description_selection(self.env)).get(rec.job_status).upper()
            if rec.source_document_display_name:
                if name:
                    name += " | "
                name += rec.source_document_display_name
            if rec.job_type_id:
                if name:
                    name += " | "
                name += rec.job_type_id.name
            if rec.job_employee_id:
                if name:
                    name += " | "
                name += rec.job_employee_id.name
            if rec.job_vehicle_id:
                if name:
                    name += " | "
                name += rec.job_vehicle_id.name
            if rec.internal_notes:
                if name:
                    name += " | "
                name += rec.internal_notes
            res.append((rec.id, name))
        return res

    attch_ids = fields.Many2many(related="schedule_id.attch_ids", readonly=False)

    internal_notes = fields.Text(related="schedule_id.internal_notes", store=True, readonly=False, force_save=True)
    html_data_src_doc = fields.Html(related='schedule_id.html_data_src_doc', readonly=False, force_save=True)
    html_link_to_src_doc = fields.Html(related='schedule_id.html_link_to_src_doc', readonly=False, force_save=True, store=True)
    source_document_display_name = fields.Char(related='schedule_id.source_document_display_name', readonly=False, force_save=True)
    active = fields.Boolean(default=True)
    schedule_id = fields.Many2one('technical.job.schedule', ondelete='cascade')
    job_type_id = fields.Many2one(related="schedule_id.job_type_id", force_save=True, readonly=False, store=True)
    res_model = fields.Char(related="schedule_id.res_model", force_save=True, store=True, readonly=False)
    res_id = fields.Integer(related="schedule_id.res_id", force_save=True, store=True, readonly=False)
    date_status = fields.Datetime(related="schedule_id.date_status")
    job_employee_id = fields.Many2one('hr.employee', string="Empleado")
    job_vehicle_id = fields.Many2one('fleet.vehicle', string="Vehículo")
    date_schedule = fields.Datetime(related="schedule_id.date_schedule", force_save=True, readonly=False, store=True)
    user_id = fields.Many2one(related="schedule_id.user_id", force_save=True, readonly=False, store=True)
    job_duration = fields.Float(related="schedule_id.job_duration", force_save=True, readonly=False, store=True )
    job_status = fields.Selection(related="schedule_id.job_status", force_save=True, readonly=False, store=True, default='to_do' )
    job_employee_ids = fields.Many2many(related='schedule_id.job_employee_ids', force_save=True, readonly=False )
    job_vehicle_ids = fields.Many2many(related='schedule_id.job_vehicle_ids', force_save=True, readonly=False)

    minutes_in_job = fields.Float(related='schedule_id.minutes_in_job', force_save=True)
    start_tracking_time = fields.Datetime(related='schedule_id.start_tracking_time', force_save=True)

    def stop_tracking(self):
        if self.schedule_id:
            self.schedule_id.stop_tracking()

    def start_tracking(self):
        if self.schedule_id:
            self.schedule_id.start_tracking()
    @api.depends('date_schedule', 'job_duration')
    def get_end_time(self):
        for record in self:
            record.end_time = record.date_schedule + timedelta(hours=record.job_duration) if record.date_schedule else False
    end_time = fields.Datetime(compute=get_end_time, store=True)


class TechnicalJobMixin(models.AbstractModel):
    _name = 'technical.job.mixing'

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("update_assistant_id", False):
            self.env['technical.job.assistant'].browse(self.env.context.get("update_assistant_id", False)).related_rec_fields()
        return res

    @api.depends('customer_availability_type', 'customer_visit_datetime')
    def visit_job_generation(self):
        config = self.env['technical.job.assistant.config'].search([('name', '=', 'Visita medición')])
        for record in self:
            if record._name == "crm.lead":
                    if config and record.stage_id.name == 'Visita' and \
                            record.customer_availability_type == 'specific_date' and record.customer_visit_datetime and \
                            not record.show_technical_schedule_job_ids.filtered(
                                lambda x: x.job_type_id.id == config[0].technical_job_type_id.id):
                        record.write({'technical_schedule_job_ids': [(0, 0,
                                                                      {'res_model': record._name,
                                                                       'job_status': 'confirmed',
                                                                       'res_id': record.id,
                                                                       'job_employee_ids': [(6, 0, config[
                                                                           0].technical_job_type_id.default_job_employee_ids.mapped('id'))],
                                                                       'job_vehicle_ids': [(6, 0, config[
                                                                           0].technical_job_type_id.default_job_vehicle_ids.mapped('id'))],
                                                                       'job_type_id': config[
                                                                           0].technical_job_type_id.id,
                                                                       'job_duration': config[
                                                                           0].technical_job_type_id.default_duration_hs,
                                                                       'user_id': config[
                                                                           0].responsible_user_id.id,
                                                                       'date_schedule': record.customer_visit_datetime})]})
            record.trigger_visit_job_generation = True if record.trigger_visit_job_generation else False



    trigger_visit_job_generation = fields.Boolean(store=True, compute=visit_job_generation)
    visit_payment_type = fields.Selection(string="Política de cobro", selection=[('free','Sin cargo'), ('to_bill','Con cargo')])
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

    technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', order='date_schedule DESC')
    @api.depends('technical_schedule_job_ids','technical_schedule_job_ids.date_schedule')
    def show_technical_jobs(self):
        for record in self:
            record.show_technical_schedule_job_ids = [(6,0,record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule).mapped('id'))]

    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=show_technical_jobs, string="Trabajos técnicos", order='date_schedule DESC')

    @api.depends('technical_schedule_job_ids','technical_schedule_job_ids.minutes_in_job')
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
            active_jobs = sorted(record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule and x.job_status not in ('done', 'cancel')), key=lambda x: x.date_schedule)
            if active_jobs:
                res = active_jobs[0].id
            record.next_active_job_id = res
            tjas = self.env['technical.job.assistant'].search([('create_uid','=',self.env.user.id), ('res_id','=',record.id), ('res_model','=',record._name)])
            for tja in tjas:
                tja.related_rec_fields()

    next_active_job_id = fields.Many2one('technical.job.schedule', compute=get_next_job, store=True)

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
            'default_res_model': self._name,
            'default_user_id': self.env.user.id,
            'default_mode': "week" if self.env.user.has_group('roc_custom.technical_job_planner') else "day",
            'initial_date': False,
        }
        #import pdb;pdb.set_trace()
        return action


class CrmLead(models.Model,TechnicalJobMixin):
    _inherit = 'crm.lead'

    def get_job_data(self):
        data = ''
        if self.visit_payment_type:
            data += "<strong>" + dict(self._fields['visit_payment_type']._description_selection(self.env)).get(self.visit_payment_type) + "<strong/><br/><br/>"
        if self.type_of_client:
            data += "Tipo de cliente: " + dict(self._fields['type_of_client']._description_selection(self.env)).get(self.type_of_client) + "<br/><br/>"
        if self.mobile or self.mobile_partner or self.phone:
            phone_number = self.mobile or self.mobile_partner or self.phone
            data += f"""
                <a href='tel:{phone_number}'><br/>
                   📲 Llamar Cliente<br/><br/>
                </a>
                
            """
        if self.address_label:
            data += "Dirección: " + self.address_label + "<br/><br/>"
        if self.customer_availability_info:
            data += self.customer_availability_info + "<br/><br/>"
        if self.visit_internal_notes:
            data += self.visit_internal_notes + "<br/><br/>"
        return data

    address_label = fields.Char(
        string='Address Label',
        compute='_compute_address_label',
    )

    @api.depends('street', 'street2', 'city', 'zip', 'state_id')
    def _compute_address_label(self):
        for lead in self:
            address_components = [lead.street, lead.street2, lead.city, lead.zip]
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
        string='Address Label',
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
        string='Address Label',
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

    def get_job_data(self):
        return self.address_label

    address_label = fields.Char(
        string='Address Label',
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
