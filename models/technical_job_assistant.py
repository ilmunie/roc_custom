import datetime
from odoo import fields, models, api, SUPERUSER_ID
from dateutil.relativedelta import relativedelta

class TechnicalJobAssistantConfig(models.Model):
    _name = 'technical.job.assistant.config'

    name = fields.Char()
    model_id = fields.Many2one('ir.model', domain=[('model', 'in', ('stock.picking', 'crm.lead','mrp.production','sale.order','purchase.order'))])
    model_name = fields.Char(related='model_id.model')
    domain_condition = fields.Char()
    technical_job_type_id = fields.Many2one('technical.job.type')
    responsible_user_id = fields.Many2one('res.users')
    date_field_id = fields.Many2one('ir.model.fields')
    date_field_tag = fields.Char()


class TechnicalJobAssistant(models.Model):
    _name = 'technical.job.assistant'

    @api.model
    def weeks_difference(self, input_date):
        """
        Calculates the number of weeks between the input_date and today's date.

        :param input_date: The date to compare with today's date.
        :type input_date: datetime.datetime, datetime.date or str in 'YYYY-MM-DD' format
        :return: The number of weeks difference.
        :rtype: int
        """
        # Ensure input_date is a datetime.date object
        if isinstance(input_date, str):
            input_date = datetime.datetime.strptime(input_date, '%Y-%m-%d').date()
        elif isinstance(input_date, datetime.datetime):
            input_date = input_date.date()
        elif not isinstance(input_date, datetime.date):
            raise ValueError(
                "The input_date must be a date object, datetime object, or a string in 'YYYY-MM-DD' format")
        today = datetime.date.today()
        # Calculate the Monday of the week for both dates
        start_of_week_input_date = input_date - relativedelta(days=input_date.weekday())
        start_of_week_today = today - relativedelta(days=today.weekday())
        # Calculate the difference in weeks
        weeks_difference = (start_of_week_input_date - start_of_week_today).days // 7
        return weeks_difference

    @api.depends('html_data_src_doc', 'next_active_job_id', 'next_active_job_date')
    def _compute_week_action_group(self):
        """
            -->  Urgente (no coordinado y marcado como urgente por comercial/coordinador)
            -->  Esperando coordinacion (no coordinado con info de disponibilidad cliente agregada por por comercial/coordinador)
            -->  Recoordinar/Aplazado (coordinaciones de semanas anteriores y trabajos marcados por tecnico en stand-by)
            -->  Sin coordinar (sin data de disponibilidad del cliente y sin coordinar)
            -->  Coordinado esta semana (con trabajos que vencen en la semana en curso puede contener cosas que vencieron ayer siempre y cuando sean de la misma semana)
            -->  Coordinado en x semanas (trabajos coordinados para el futuro 2 semanas #2+ Semanas)
        """
        for record in self:
            res = ''
            if not record.next_active_job_id:
                if record.html_data_src_doc and "URGENT" in record.html_data_src_doc:
                    res = "1. Urgente"
                elif record.job_status == "waiting_job":
                    res = "2. Esperando coordinacion"
                elif not record.next_active_job_id:
                    res = "4. Sin coordinar"
            else:
                if record.job_status == 'stand_by':
                    res = f"3. Recoordinar / Aplazado"
                else:
                    date_to_use = record.next_active_job_date
                    if date_to_use:
                        week_diff = self.weeks_difference(date_to_use)
                        if week_diff == 0:
                            res = "5. Esta semana"
                        elif week_diff <= -1:
                            res = f"3. Recoordinar / Aplazado"
                        elif week_diff < 2:
                            res = f"6. En {week_diff} Semanas"
                        else:
                            res = f"7. +1 Semanas"
            record.week_action_group = res

    week_action_group = fields.Char(string='Week Action Group', compute='_compute_week_action_group', store=True)

    @api.depends('date_field_value', 'next_active_job_date')
    def _compute_week_group(self):
        for record in self:
            date_to_use = record.date_field_value or record.next_active_job_date
            if date_to_use:
                week_diff = self.weeks_difference(date_to_use)
                if week_diff == 0:
                    record.week_group = "0 - Esta semana"
                elif week_diff <= -1 and week_diff > -5:
                    record.week_group = f"{week_diff} Semanas"
                elif week_diff <= -5:
                    record.week_group = f"-5 - Hace más de 5 semanas"
                else:
                    record.week_group = "Sin definir"
            else:
                record.week_group = "Sin fecha"
    week_group = fields.Char(string='Week Group', compute='_compute_week_group', store=True)

    def compute_dec_danger(self):
        for record in self:
            res = False
            if record.html_data_src_doc and "URGENT" in record.html_data_src_doc:
                res = True
            record.dec_danger = res
    dec_danger = fields.Boolean(compute=compute_dec_danger)
    def edit_next_job(self):
        self.ensure_one()
        if self.res_id and self.res_model:
            context = {'update_assistant_id': self.id}
            res_id = self.env['technical.job'].search([('schedule_id', '=', self.next_active_job_id.id)])
            action = {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'context': context,
                'view_mode': 'form',
                'res_model': 'technical.job',
                'target': 'new',
                'res_id': res_id[0].id if res_id else False,
            }
            return action
    def see_src_document(self):
        self.ensure_one()
        context = {'update_assistant_id': self.id}
        if self.res_id and self.res_model:
            action = {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'context': context,
                'res_model': self.res_model,
                'target': 'new',
                'res_id': self.res_id,
            }
            return action

    def see_job_in_calendar(self):
        self.ensure_one()
        if self.next_active_job_id:
            action = self.next_active_job_id.open_in_calendar_view()
            real_rec = self.env[self.res_model].browse(self.res_id)
            action_sch = real_rec.action_schedule_job() if real_rec else False
            if action_sch:
                action["context"].update(action_sch["context"])
            action["context"].update({'from_calendar': True, 'initial_date': self.next_active_job_date})
            return action
    def action_schedule_job(self):
        self.ensure_one()
        if self.res_model and self.res_id:
            real_rec = self.env[self.res_model].browse(self.res_id)
            action = real_rec.action_schedule_job()
            action["context"].update({'from_calendar': True})
            return action

    config_id = fields.Many2one('technical.job.assistant.config', string="Configuración")
    responsible_user_id = fields.Many2one(related='config_id.responsible_user_id', store=True, string="Usuario Responsable")
    def start_assistant(self):
        self.env['technical.job.assistant'].search([('create_uid','=', self.env.user.id)]).unlink()
        configs = self.env['technical.job.assistant.config'].search([('id', '!=', 0)])
        recs_to_create = []
        user_type = 'planner' if self.env.user.has_group('roc_custom.technical_job_planner') else 'user'
        for config in configs:
            domain_to_check = eval(config.domain_condition) if config.domain_condition else []
            matching_records = self.env[config.model_id.model].search(domain_to_check)
            recs_to_create.extend([{'res_model': rec._name, 'res_id': rec.id, 'config_id': config.id} for rec in matching_records])
        self.env['technical.job.assistant'].create(recs_to_create)
        return {
            'name': "Planificación de Operaciones",
            'res_model': 'technical.job.assistant',
            'type': 'ir.actions.act_window',
            'context': {
                    'search_default_assigned_to_me': 1 if user_type == 'planner' else 0,
                    'search_default_myjobs': 1 if user_type == 'user' else 0,
                    'search_default_week_action_group': 1
                },
            'domain': [('create_uid', '=', self.env.user.id)],
            'views': [(self.env.ref('roc_custom.technical_job_assistant_tree_view').id, 'tree'),(False,'kanban')] if user_type=='planner' else [(False,'kanban'),(self.env.ref('roc_custom.technical_job_assistant_tree_view').id, 'tree')] ,
        }

    res_model = fields.Char(string="Modelo")
    res_id = fields.Integer(string="ID")

    @api.depends('res_model','res_id')
    def related_rec_fields(self):
        for record in self:
            show_technical_schedule_job_ids = []
            html = ""
            html_data_src_doc = ""
            next_job = False
            technical_job_count = 0
            date_field_value = False
            tag_ids = [(5,)]
            if record.res_model and record.res_id:
                real_rec = self.env[record.res_model].browse(record.res_id)
                if real_rec:
                    tag_ids = [(6, 0, real_rec.technical_job_tag_ids.mapped('id'))]
                    html_data_src_doc = real_rec.get_job_data()
                    technical_job_count = real_rec.technical_job_count
                    show_technical_schedule_job_ids = [(6,0,real_rec.show_technical_schedule_job_ids.mapped('id'))]
                    date_field_value = real_rec[record.config_id.date_field_id.name]
                    next_job = real_rec.next_active_job_id
                    html += "<table style='border-collapse: collapse; border: none;'>"
                    html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(
                        record.res_id,
                        record.res_model)
                    html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(real_rec.display_name)

            record.technical_job_tag_ids = tag_ids
            record.date_field_value = date_field_value.date()
            record.technical_job_count = technical_job_count
            record.html_link_to_src_doc = html
            record.html_data_src_doc = html_data_src_doc
            record.next_active_job_id = next_job.id if next_job else False
            record.show_technical_schedule_job_ids = show_technical_schedule_job_ids if show_technical_schedule_job_ids else False

    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=related_rec_fields, store=True, string="Operaciones")
    technical_job_tag_ids = fields.Many2many(comodel_name='technical.job.tag', compute=related_rec_fields, store=True, string="Etiquetas")
    next_active_job_id = fields.Many2one('technical.job.schedule', compute=related_rec_fields, store=True, string= "Próx. Planificación", ondelete='SET NULL')

    next_active_job_date = fields.Datetime(string="Fecha próx. planificación", related='next_active_job_id.date_schedule', store=True)
    date_field_value = fields.Datetime(string="Fecha interés")
    date_field_tag = fields.Char(string="Solicitud", related="config_id.date_field_tag")
    html_link_to_src_doc = fields.Html(compute=related_rec_fields, store=True, string="Documento origen")
    html_data_src_doc = fields.Html(compute=related_rec_fields, store=True, string="Data")
    technical_job_count = fields.Integer(string='Planificaciones activas')
    next_active_job_type_id = fields.Many2one(related='next_active_job_id.job_type_id', store=True, string="Tipo próx. trabajo")

    @api.depends('next_active_job_id', 'next_active_job_id.job_vehicle_ids', 'next_active_job_id.job_employee_ids')
    def compute_related_resources(self):
        for record in self:
            record.next_job_vehicle_ids = [(6,0,record.next_active_job_id.job_vehicle_ids.mapped('id'))] if record.next_active_job_id else False
            record.next_job_employee_ids = [(6,0,record.next_active_job_id.job_employee_ids.mapped('id'))] if record.next_active_job_id else False
    next_job_vehicle_ids = fields.Many2many('fleet.vehicle', compute=compute_related_resources, store=True, string="Vehículo")
    next_job_employee_ids = fields.Many2many('hr.employee', compute=compute_related_resources, store=True, string="Personal visita")

    @api.depends('next_active_job_id')
    def compute_assistant_status(self):
        for record in self:
            job_status = 'no_job'
            next_job = record.next_active_job_id
            if record.res_model and record.res_id:
                real_rec = self.env[record.res_model].browse(record.res_id)
                if real_rec:
                    technical_job = record.config_id.technical_job_type_id.id if record.config_id and record.config_id.technical_job_type_id else False
                    if technical_job:
                        if record.res_id and record.res_model == 'crm.lead' and \
                                not real_rec.show_technical_schedule_job_ids and \
                                real_rec.customer_availability_type in ('hour_range', 'week_availability', 'urgent'):
                            job_status = 'waiting_job'
                        elif next_job and next_job.job_type_id and next_job.job_type_id.id == technical_job:
                            job_status = next_job.job_status
                        else:
                            jobs = real_rec.show_technical_schedule_job_ids.filtered(lambda
                                                                                         x: x.job_type_id and x.job_type_id.id == technical_job and x.job_status != 'cancel')
                            if jobs:
                                job_status = sorted(jobs, key=lambda r: r.date_schedule, reverse=True)[0].job_status
            record.job_status = job_status


    job_status = fields.Selection([('no_job','Sin planificaciones'),
                                   ('waiting_job', 'Esperando coordinacion'),
                                   ('to_do', 'Planificado'),
                                   ('confirmed', 'Confirmado'),
                                   ('stand_by', 'Aplazado'),
                                   ('done', 'Terminado'),
                                   ], store=True, compute=compute_assistant_status, string="Estado")


