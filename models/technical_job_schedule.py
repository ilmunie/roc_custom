
from odoo import fields, models, api
from datetime import timedelta
import pytz

class TechnicalJobStatusChange(models.Model):
    _name = 'technical.job.status.change'

    schedule_id = fields.Many2one('technical.job.schedule')
    date = fields.Datetime()
    job_status = fields.Char()

class TechnicalJobSchedule(models.Model):
    _name = 'technical.job.schedule'
    order = 'date_schedule DESC'
    _inherit = ['mail.thread']


    @api.depends('status_change_ids')
    def compute_datetime_last_status(self):
        for record in self:
            if record.status_change_ids:
                record.datetime_in_status = sorted(record.status_change_ids, key=lambda r: r.date, reverse=True)[0].date #+ timedelta(days=1)
            else:
                record.datetime_in_status = record.write_date or record.create_date

    datetime_in_status = fields.Datetime(compute=compute_datetime_last_status, store=True, string="Cambio de estado")
    status_change_ids = fields.One2many('technical.job.status.change','schedule_id')

    @api.depends('job_status')
    def compute_status_change(self):
        for record in self:
            if record.job_status:
                self.env['technical.job.status.change'].create({
                    'schedule_id': record.id,
                    'date': fields.Datetime.now(),
                    'job_status': record.job_status
                })
            record.trigger_status_change = False if record.trigger_status_change else True
    trigger_status_change = fields.Boolean(compute=compute_status_change, store=True)

    checklist_line_ids = fields.One2many('technical.job.checklist.assistant.line', 'technical_schedule_id')

    def see_sale_order(self):
        if len(self.sale_order_ids.mapped('id')) == 1:
            return {
                'name': "Orden de venta",
                'res_model': 'sale.order',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_id': self.sale_order_ids[0].id,
            }
        else:
            return {
                'name': "Ordenes de venta",
                'res_model': 'sale.order',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,kanban,form',
                'domain': [('id', 'in', self.sale_order_ids.mapped('id'))],
            }
    sale_order_ids = fields.Many2many('sale.order')


    def get_job_data(self):
        return False

    def compute_time_register_metrics(self):
        for record in self:
            disp_min = 0
            bill_min = 0
            if record.time_register_ids:
                disp_min = sum(record.time_register_ids.filtered(lambda x: x.displacement).mapped('total_min'))
                bill_min = sum(record.time_register_ids.filtered(lambda x: not x.displacement).mapped('total_min'))
            record.displacement_total_min = disp_min
            record.billable_total_min = bill_min

    displacement_total_min = fields.Float(compute=compute_time_register_metrics, string="Desplazamiento total (min)")
    billable_total_min = fields.Float(compute=compute_time_register_metrics, string="Tiempo total en domicilio (min)")

    time_register_ids = fields.One2many('technical.job.time.register', 'technical_job_schedule_id')

    visit_internal_notes = fields.Text()
    technical_job_count = fields.Integer()

    def write(self, vals):
        res = super().write(vals)
        if self.res_id and self.res_model:
            real_rec = self.env[self.res_model].browse(self.res_id)
            sync_vals = {}
            if 'job_employee_ids' in vals:
                if real_rec.job_employee_ids.ids != self.job_employee_ids.ids:
                    sync_vals['job_employee_ids'] = vals.get('job_employee_ids', [(5,)])
            if 'job_vehicle_ids' in vals:
                if real_rec.job_vehicle_ids.ids != self.job_vehicle_ids.ids:
                    sync_vals['job_vehicle_ids'] = vals.get('job_vehicle_ids', [(5,)])
            if 'technical_job_tag_ids' in vals:
                if real_rec.technical_job_tag_ids.ids != self.technical_job_tag_ids.ids:
                    sync_vals['technical_job_tag_ids'] = vals.get('technical_job_tag_ids', [(5,)])
            if 'internal_notes' in vals:
                if real_rec.visit_internal_notes != self.internal_notes:
                    sync_vals['visit_internal_notes'] = vals.get('internal_notes', '')
            if 'estimated_visit_revenue' in vals:
                if real_rec.estimated_visit_revenue != self.estimated_visit_revenue:
                    sync_vals['estimated_visit_revenue'] = vals.get('estimated_visit_revenue', 0)
            if 'job_duration' in vals:
                if real_rec.job_duration != self.job_duration:
                    sync_vals['job_duration'] = vals.get('job_duration', 0)
            if 'visit_payment_type' in vals:
                if real_rec.visit_payment_type != self.visit_payment_type:
                    sync_vals['visit_payment_type'] = vals.get('visit_payment_type', False)
            if 'reminder_date' in vals:
                if real_rec.reminder_date != self.reminder_date:
                    sync_vals['reminder_date'] = vals.get('reminder_date', False)
            if 'reminder_user_id' in vals:
                user_real_rec = real_rec.reminder_user_id.id if real_rec.reminder_user_id else False
                if vals.get('reminder_user_id', False) != user_real_rec:
                    sync_vals['reminder_user_id'] = vals.get('reminder_user_id', False)
            if 'visit_priority' in vals:
                if real_rec.visit_priority != self.visit_priority:
                    sync_vals['visit_priority'] = vals.get('visit_priority', 0)
            if 'job_categ_ids' in vals:
                if real_rec.job_categ_ids.ids != self.job_categ_ids.ids:
                    sync_vals['job_categ_ids'] = vals.get('job_categ_ids', [(5,)])
            if sync_vals:
                real_rec.write(sync_vals)

        #if self.res_model and self.res_id and :
        #    real_rec = self.env[self.res_model].browse(self.res_id)
        #    body = "Ha modificado la nota interna de la proxima operacion<br/>"nñ. -|
        #    body += vals['internal_notes']
        #    real_rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment')
        return res

    def stop_tracking(self):
        self.ensure_one()
        cr = self.env.cr
        now = fields.Datetime.now()
        cr.execute("SELECT start_tracking_time, minutes_in_job FROM technical_job_schedule WHERE id = %s", (self.id,))
        row = cr.fetchone()
        start_time = row[0] if row else None
        current_minutes = row[1] if row else 0.0
        if start_time:
            time_diff_minutes = (now - start_time).total_seconds() / 60
            new_minutes = (current_minutes or 0.0) + time_diff_minutes
            cr.execute("UPDATE technical_job_time_register SET end_time = %s WHERE technical_job_schedule_id = %s AND end_time IS NULL", (now, self.id))
            cr.execute("UPDATE technical_job_schedule SET minutes_in_job = %s, start_tracking_time = NULL WHERE id = %s", (new_minutes, self.id))
            self.invalidate_cache()
        return True

    def start_tracking(self):
        self.ensure_one()
        cr = self.env.cr
        now = fields.Datetime.now()
        cr.execute("""
            INSERT INTO technical_job_time_register (technical_job_schedule_id, start_time, create_uid, write_uid, create_date, write_date)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (self.id, now, self.env.uid, self.env.uid, now, now))
        cr.execute("UPDATE technical_job_schedule SET start_tracking_time = %s WHERE id = %s", (now, self.id))
        self.invalidate_cache()
        return True



    minutes_in_job = fields.Float(string="Minutos trabajados")
    start_tracking_time = fields.Datetime()
    arrive_time = fields.Datetime(string="Horario Entrada")
    out_time = fields.Datetime(string="Horario Salida")

    #fields for displacement register
    displacement_start_datetime = fields.Datetime(string='Inicio Desplazamiento')

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

    def open_in_calendar_view(self):
        action = self.env.ref('roc_custom.action_technical_job').read()[0]
        action['context'] = {
                'default_mode': 'week' if self.env.user.has_group('roc_custom.technical_job_planner') else 'day',
                'initial_date': self.date_schedule,
                'search_default_res_model': self.res_model,
                'search_default_res_id': self.res_id,
        }
        action['target'] = 'main'
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
    html_data_src_doc = fields.Html(compute=get_data_src_doc, string="Info trabajo a realizar")


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

    estimated_visit_revenue = fields.Float(string="Estimado (EUR)")
    visit_payment_type = fields.Selection(string="Política de cobro", selection=[('free','Sin cargo'), ('to_bill','Con cargo')])
    visit_priority = fields.Selection(string="Prioridad Visita", selection=[('0', 'Sin definir'), ('1','Baja'), ('2','Media'), ('3','Alta')])
    job_categ_ids = fields.Many2many('technical.job.categ', string="Categoria")
    job_type_id = fields.Many2one('technical.job.type', string="Tipo trabajo")
    res_model = fields.Char()
    res_id = fields.Integer()
    job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita", domain=[('technical','=',True)])
    job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")
    technical_job_tag_ids = fields.Many2many('technical.job.tag', string="Etiquetas")
    reminder_date = fields.Date(string="A recordar")
    reminder_user_id = fields.Many2one('res.users', string="Usuario Recordatorio")
    date_schedule = fields.Datetime(string="Fecha a visitar")
    user_id = fields.Many2one('res.users', store=True, string="Responsable")
    job_duration = fields.Float(string="Tiempo trabajo (hs.)")
    job_status = fields.Selection(
        selection=[('to_do', 'Planificado'), ('confirmed', 'Confirmado'), ('stand_by', 'Aplazado'), ('done', 'Terminado'), ('cancel', 'Cancelado')],
        string="Estado", default='to_do')
    internal_notes = fields.Text(string="Notas internas")

    @api.depends('sync_attachments')
    def get_attch(self):
        for record in self:
            att = self.env['ir.attachment'].search([('res_id','=',record.id),('res_model','=','technical.job.schedule'), ('added_from_technical_job', '=', True)])
            record.attch_ids = [(6,0, att.mapped('id'))]

    attch_ids = fields.Many2many('ir.attachment',
                                 string="Adjuntos",
                                 compute=get_attch, store=True)

    sync_attachments = fields.Boolean()

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
            # Batch deactivate existing jobs instead of one-by-one
            existing_jobs = self.env['technical.job'].search([('schedule_id', '=', rec.id)])
            if existing_jobs:
                existing_jobs.write({'active': False})

            # Build all vals at once and batch-create
            vals_list = []
            if rec.job_employee_ids:
                for employee in rec.job_employee_ids:
                    if rec.job_vehicle_ids:
                        for vehicle in rec.job_vehicle_ids:
                            vals_list.append({
                                'job_employee_id': employee.id,
                                'job_vehicle_id': vehicle.id,
                                'schedule_id': rec.id,
                            })
                    else:
                        vals_list.append({
                            'job_employee_id': employee.id,
                            'job_vehicle_id': False,
                            'schedule_id': rec.id,
                        })
            else:
                if rec.job_vehicle_ids:
                    for vehicle in rec.job_vehicle_ids:
                        vals_list.append({
                            'job_employee_id': False,
                            'job_vehicle_id': vehicle.id,
                            'schedule_id': rec.id,
                        })
                else:
                    vals_list.append({
                        'job_employee_id': False,
                        'job_vehicle_id': False,
                        'schedule_id': rec.id,
                    })
            if vals_list:
                self.env['technical.job'].create(vals_list)

            rec.trigger_refresh_jobs = False if rec.trigger_refresh_jobs else False