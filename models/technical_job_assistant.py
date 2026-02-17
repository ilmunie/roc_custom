import datetime
from odoo import fields, models, api, SUPERUSER_ID
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo.exceptions import ValidationError, UserError
from random import randint

class SeeFullHtmlMessage(models.TransientModel):
    _name = 'see.full.html.message'

    html = fields.Html(nolabel="1", readonly=True)
    html_title = fields.Html(nolabel="1", readonly=True)


class TechnicalJobAssistantConfig(models.Model):
    _name = 'technical.job.assistant.config'

    name = fields.Char()
    model_id = fields.Many2one('ir.model', domain=[('model', 'in', ('stock.picking','helpdesk.ticket', 'crm.lead','mrp.production','sale.order','purchase.order'))])
    model_name = fields.Char(related='model_id.model')
    domain_condition = fields.Char()
    technical_job_type_id = fields.Many2one('technical.job.type')
    responsible_user_id = fields.Many2one('res.users')
    date_field_id = fields.Many2one('ir.model.fields')
    date_field_tag = fields.Char()
    def _get_default_color(self):
        return randint(1, 11)
    color = fields.Integer('Color', default=_get_default_color)

class TechnicalJobCalendarQuickResolve(models.TransientModel):
    _name = 'technical.job.calendar.quick.resolve'

    line_ids = fields.Many2many('technical.job.assistant', 'tj_quick_resolve_line_ids_rel', 'line_id', 'wiz_id')

    @api.model
    def default_get(self, fields):
        recs = self.env['technical.job.assistant'].search([('create_uid','=', self.env.user.id), ('technical_job_tag_ids.name', 'ilike', self.env.ref('roc_custom.tj_tag_quick_resolve').name)])
        if not recs:
            raise ValidationError("No hay registros esperando coordinación rápida")
        result = super(TechnicalJobCalendarQuickResolve, self).default_get(fields)
        result['line_ids'] = [(6, 0, recs.mapped('id'))]
        return result

class TechnicalJobAssistant(models.Model):
    _name = 'technical.job.assistant'

    def quick_job_resolution(self):
        action = self.start_assistant()
        return {
            'name': "Asignación Rápida",
            'res_model': 'technical.job.calendar.quick.resolve',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'view_mode': 'form',
            'view_id': self.env.ref('roc_custom.technical_job_calendar_quick_resolve').id,
        }

    def action_quick_resolve(self):
        self.technical_job_tag_ids = [(3, self.env.ref('roc_custom.tj_tag_quick_resolve').id)]
        return self.with_context(quick_resolve=True).action_schedule_job()

    def edit_tags(self):
        action = self.edit_internal_note()
        return action

    def write(self, vals):
        res = super().write(vals)
        if self.res_id and self.res_model:
            if self.res_model == 'technical.job.schedule':
                matched_jobs = self.env['technical.job'].search([('schedule_id', '=', self.res_id)])
                if matched_jobs:
                    real_rec = matched_jobs[0]
                else:
                    real_rec = self.env[self.res_model].browse(self.res_id)

            else:
                real_rec = self.env[self.res_model].browse(self.res_id)
            if real_rec:
                if 'internal_notes' in vals:
                    if self.res_model == 'technical.job.schedule':
                        if real_rec.internal_notes != self.internal_notes:
                            real_rec.internal_notes = self.internal_notes
                    else:
                        if real_rec.visit_internal_notes != self.internal_notes:
                            real_rec.visit_internal_notes = self.internal_notes
                if 'job_employee_ids' in vals:
                    if real_rec.job_employee_ids.mapped('id') != self.job_employee_ids.mapped('id'):
                        real_rec.job_employee_ids = vals.get('job_employee_ids', [(5,)])
                if 'job_vehicle_ids' in vals:
                    if real_rec.job_vehicle_ids.mapped('id') != self.job_vehicle_ids.mapped('id'):
                        real_rec.job_vehicle_ids = vals.get('job_vehicle_ids', [(5,)])
                if 'technical_job_tag_ids' in vals:
                    if real_rec.technical_job_tag_ids.mapped('id') != self.technical_job_tag_ids.mapped('id'):
                        real_rec.technical_job_tag_ids = vals.get('technical_job_tag_ids', [(5,)])
                if 'reminder_date' in vals:
                    if real_rec.reminder_date != self.reminder_date:
                        real_rec.reminder_date = vals.get('reminder_date', False)
                if 'reminder_user_id' in vals:
                    rec_user = real_rec.reminder_user_id.id if real_rec.reminder_user_id else False
                    assistant_user = vals.get('reminder_user_id', False)
                    if rec_user != assistant_user:
                        real_rec.reminder_user_id = vals.get('reminder_user_id', False)
                if 'visit_priority' in vals:
                    if real_rec.visit_priority != self.visit_priority:
                        real_rec.visit_priority = vals.get('visit_priority', False)
                if 'job_duration' in vals:
                    if real_rec.job_duration != self.job_duration:
                        real_rec.job_duration = vals.get('job_duration', False)
                if 'estimated_visit_revenue' in vals:
                    if real_rec.estimated_visit_revenue != self.estimated_visit_revenue:
                        real_rec.estimated_visit_revenue = vals.get('estimated_visit_revenue', False)
                if 'job_categ_ids' in vals:
                    if real_rec.job_categ_ids.mapped('id') != self.job_categ_ids.mapped('id'):
                        real_rec.job_categ_ids = vals.get('job_categ_ids', [(5,)])
        return res

    def open_form_partner(self):
        action = self.env.ref('roc_custom.action_technical_job_partner_form').read()[0]
        context = {'update_assistant_id': self.id}
        action['context'] = context
        if self.res_model == 'crm.lead':
            real_rec = self.env[self.res_model].browse(self.res_id)
            if real_rec.partner_id:
                action["res_id"] = real_rec.id
            else:
                UserWarning('No hay una cliente asociado al registro')
        else:
            UserWarning('No hay una configuración de Cliente Definida')
        return action

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

    @api.depends('html_data_src_doc', 'next_active_job_id', 'next_active_job_date', 'technical_job_tag_ids')
    def _compute_week_action_group(self):
        """
            -->  Urgente (no coordinado y marcado como urgente por comercial/coordinador)
            -->  Esperando confirmacion (no coordinado con info de disponibilidad cliente agregada por por comercial/coordinador)
            -->  Recoordinar/Aplazado (coordinaciones de semanas anteriores y trabajos marcados por tecnico en stand-by)
            -->  Sin coordinar (sin data de disponibilidad del cliente y sin coordinar)
            -->  Coordinado esta semana (con trabajos que vencen en la semana en curso puede contener cosas que vencieron ayer siempre y cuando sean de la misma semana)
            -->  Coordinado en x semanas (trabajos coordinados para el futuro 2 semanas #2+ Semanas)
        """
        for record in self:
            res = ''
            categ_tag_list_name = record.technical_job_tag_ids.filtered(lambda x: x.category_in_job_assistant).sorted(key=lambda tag: tag.name).mapped('name')
            if categ_tag_list_name:
                    res = f"3.{','.join(categ_tag_list_name)}"
            elif record.res_model == 'technical.job.schedule':
                date_to_use = record.next_active_job_id.date_schedule.date() if record.next_active_job_id else datetime.date.today()
                today = datetime.date.today()
                if date_to_use < today:
                    res = f"6. Recoordinar (Vencidos)"
                else:
                    res = f"4. Coordinado (Esta semana)"
            elif not record.next_active_job_id:
                if record.html_data_src_doc and "Urgente" in record.html_data_src_doc:
                    res = "1. Urgente"
                else:
                    res = "2. No coordinado (A analizar)"
            else:
                if record.job_status == 'stand_by':
                    res = f"5. Aplazado (Stand-by)"
                else:
                    date_to_use = record.next_active_job_date
                    input_date = date_to_use
                    if date_to_use:
                        if isinstance(date_to_use, str):
                            input_date = datetime.datetime.strptime(date_to_use, '%Y-%m-%d').date()
                        elif isinstance(date_to_use, datetime.datetime):
                            input_date = date_to_use.date()
                        elif not isinstance(date_to_use, datetime.date):
                            raise ValueError(
                                "The input_date must be a date object, datetime object, or a string in 'YYYY-MM-DD' format")
                        today = datetime.date.today()
                        if input_date < today:
                            res = f"6. Recoordinar (Vencidos)"
                        else:
                            week_diff = self.weeks_difference(date_to_use)
                            if week_diff == 0:
                                res = "4. Coordinado (Esta semana)"
                            elif week_diff <= -1:
                                res = f"6. Recoordinar (Vencidos)"
                            elif week_diff < 2:
                                res = f"4. Coordinado (Semana que viene)"
                            else:
                                res = f"7. Coordinado +1 Semanas"
            record.week_action_group = res

    week_action_group = fields.Char(string='Week Action Group', compute='_compute_week_action_group', store=True)

    @api.depends('date_field_value', 'next_active_job_date')
    def _compute_week_group(self):
        for record in self:
            date_to_use = record.date_field_value or record.next_active_job_date
            if date_to_use and record.date_field_value:
                date_to_use = date_to_use + timedelta(days=1)
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
            if not self.next_active_job_id:
                return self.with_context(update_assistant_id=self.id).action_schedule_job()
            else:
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

    def edit_internal_note(self):
        self.ensure_one()
        context = {'update_assistant_id': self.id}
        action = {
            'name': "Edicion datos",
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'res_id': self.id,
            'res_model': 'technical.job.assistant',
            'target': 'new',
        }
        return action

    def see_all_data(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.env['see.full.html.message'].create({'html': self.html_data_src_doc, 'html_title': self.html_link_to_src_doc}).id,
            'res_model': 'see.full.html.message',
            'target': 'new',
        }
        return action


    def see_src_document(self):
        self.ensure_one()
        context = {'update_assistant_id': self.id}
        if self.res_id and self.res_model:
            if self.res_model == 'technical.job.schedule':
                job = self.env['technical.job'].search([('schedule_id', '=', self.res_id)])
                action = {
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'context': context,
                    'res_model': 'technical.job',
                    'target': 'new',
                    'res_id': job[0].id,
                }
            else:
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
        if self.res_model == 'technical.job.schedule':
            action = self.env.ref('roc_custom.action_technical_job').read()[0]
            action['context'] = {
                'default_mode': 'week' if self.env.user.has_group('roc_custom.technical_job_planner') else 'day',
                'initial_date': self.next_active_job_id.date_schedule,
                'update_assistant_id': self.id,
                'search_default_id': self.env['technical.job'].search([('schedule_id', '=', self.res_id)])[0].id,
            }
            return action
        elif self.next_active_job_id:
            action = self.next_active_job_id.open_in_calendar_view()
            real_rec = self.env[self.res_model].browse(self.res_id)
            action_sch = real_rec.action_schedule_job() if real_rec else False
            if action_sch:
                action["context"].update(action_sch["context"])
            action["context"].update({'update_assistant_id': self.id, 'from_calendar': True, 'initial_date': self.next_active_job_date})
            return action

    def action_schedule_job(self):
        self.ensure_one()
        if self.res_model and self.res_id:
            real_rec = self.env[self.res_model].browse(self.res_id)
            action = real_rec.action_schedule_job()
            action["context"].update({'from_calendar': True, 'update_assistant_id': self.id})
            return action

    config_id = fields.Many2one('technical.job.assistant.config', string="Configuración")
    color = fields.Integer(related='config_id.color')
    responsible_user_id = fields.Many2one(related='config_id.responsible_user_id', store=True, string="Usuario Responsable")

    def start_assistant(self):
        cr = self.env.cr
        uid = self.env.user.id
        user_type = 'planner' if self.env.user.has_group('roc_custom.technical_job_planner') else 'user'

        # 1) Bulk delete existing assistant records for this user via raw SQL
        #    Clean m2m relation tables dynamically, then the main table
        Assistant = self.env['technical.job.assistant']
        m2m_fields = [
            'technical_job_tag_ids', 'show_technical_schedule_job_ids',
            'job_categ_ids', 'next_job_vehicle_ids', 'next_job_employee_ids',
        ]
        for fname in m2m_fields:
            field = Assistant._fields[fname]
            rel_table = field.relation
            col1 = field.column1
            cr.execute("""
                DELETE FROM "{rel}" WHERE "{col}" IN (
                    SELECT id FROM technical_job_assistant WHERE create_uid = %s
                )
            """.format(rel=rel_table, col=col1), (uid,))
        # Also clean the quick resolve wizard m2m
        cr.execute("""
            DELETE FROM tj_quick_resolve_line_ids_rel
            WHERE line_id IN (
                SELECT id FROM technical_job_assistant WHERE create_uid = %s
            )
        """, (uid,))
        cr.execute("DELETE FROM technical_job_assistant WHERE create_uid = %s", (uid,))

        # 2) Fetch all configs
        cr.execute("""
            SELECT c.id, c.domain_condition, m.model
            FROM technical_job_assistant_config c
            JOIN ir_model m ON m.id = c.model_id
        """)
        configs = cr.fetchall()

        # 3) For each config, resolve the domain to SQL and bulk insert
        now = fields.Datetime.now()
        for config_id, domain_condition, model_name in configs:
            domain_to_check = eval(domain_condition) if domain_condition else []
            Model = self.env[model_name]
            query = Model._where_calc(domain_to_check)
            from_clause, where_clause, where_params = query.get_sql()
            if not where_clause:
                where_clause = 'TRUE'
            # Insert matching records directly into the assistant table
            cr.execute("""
                INSERT INTO technical_job_assistant
                    (res_model, res_id, config_id, create_uid, write_uid, create_date, write_date)
                SELECT
                    %s, "{table}".id, %s, %s, %s, %s, %s
                FROM {from_clause}
                WHERE {where_clause}
            """.format(
                table=Model._table,
                from_clause=from_clause,
                where_clause=where_clause,
            ), [model_name, config_id, uid, uid, now, now] + list(where_params))

        new_records = self.env['technical.job.assistant'].search([('create_uid', '=', uid)])
        new_records.related_rec_fields()
        tree_view_id = self.env.ref('roc_custom.technical_job_assistant_tree_view').id
        return {
            'name': "Planificación de Operaciones",
            'res_model': 'technical.job.assistant',
            'type': 'ir.actions.act_window',
            'context': {
                    'search_default_week_action_group': 1,
                    'search_default_configuration': 1,
                },
            'domain': [('create_uid', '=', uid)],
            'views': [(tree_view_id, 'tree'), (False, 'kanban')] if user_type == 'planner' else [(False, 'kanban'), (tree_view_id, 'tree')],
        }
    

    res_model = fields.Char(string="Modelo")
    res_id = fields.Integer(string="ID")


    def related_rec_fields(self):

        from collections import defaultdict

        # --- Phase 1: Group assistant records by res_model ---
        model_groups = defaultdict(list)  # {model_name: [assistant_record, ...]}
        for record in self:
            if record.res_model and record.res_id:
                model_groups[record.res_model].append(record)
            else:
                model_groups[False].append(record)

        # --- Phase 2: Batch-prefetch source records per model (1 query per model) ---
        real_recs_map = {}  # {(model_name, res_id): recordset}
        for model_name, records in model_groups.items():
            if not model_name:
                continue
            all_ids = [r.res_id for r in records]
            all_real = self.env[model_name].browse(all_ids).exists()
            # Force prefetch of key fields in a single query
            if all_real:
                prefetch_fields = ['display_name', 'technical_job_tag_ids', 'reminder_date',
                                   'reminder_user_id', 'estimated_visit_revenue', 'job_duration',
                                   'visit_payment_type', 'visit_priority', 'job_categ_ids',
                                   'technical_job_count']
                valid_fields = [f for f in prefetch_fields if f in self.env[model_name]._fields]
                if model_name != 'technical.job.schedule':
                    for extra in ['next_active_job_id', 'address_label', 'visit_internal_notes',
                                  'show_technical_schedule_job_ids']:
                        if extra in self.env[model_name]._fields:
                            valid_fields.append(extra)
                else:
                    for extra in ['internal_notes', 'job_status', 'date_schedule']:
                        if extra in self.env[model_name]._fields:
                            valid_fields.append(extra)
                all_real.read(valid_fields)
                for rec in all_real:
                    real_recs_map[(model_name, rec.id)] = rec

        # --- Phase 3: Pre-fetch technical.job for schedule records (1 query) ---
        schedule_res_ids = [r.res_id for r in model_groups.get('technical.job.schedule', [])]
        tj_by_schedule = {}
        if schedule_res_ids:
            tech_jobs = self.env['technical.job'].search([('schedule_id', 'in', schedule_res_ids)])
            if tech_jobs:
                tech_jobs.read(['schedule_id'])
                for tj in tech_jobs:
                    tj_by_schedule.setdefault(tj.schedule_id.id, tj)

        # --- Phase 4: Pre-fetch partner phones for non-schedule models (batch) ---
        partner_ids_to_fetch = set()
        for model_name, records in model_groups.items():
            if not model_name or model_name == 'technical.job.schedule':
                continue
            Model = self.env[model_name]
            if 'partner_id' in Model._fields:
                for rec in records:
                    real_rec = real_recs_map.get((model_name, rec.res_id))
                    if real_rec and real_rec.partner_id:
                        partner_ids_to_fetch.add(real_rec.partner_id.id)
        if partner_ids_to_fetch:
            partners = self.env['res.partner'].browse(list(partner_ids_to_fetch))
            partners.read(['phone', 'mobile', 'child_ids'])
            child_ids = set()
            for p in partners:
                child_ids.update(p.child_ids.ids)
            if child_ids:
                self.env['res.partner'].browse(list(child_ids)).read(['phone', 'mobile'])

        # --- Phase 5: Process all records using prefetched data ---
        for record in self:
            show_technical_schedule_job_ids = False
            html = ""
            address = ""
            phones = []
            internal_notes_html = ""
            html_data_src_doc = ""
            next_job = False
            internal_notes = ""
            technical_job_count = 0
            date_field_value = False
            tag_ids = [(5,)]
            estimated_visit_revenue = 0
            job_duration = 0
            visit_payment_type = False
            visit_priority = False
            job_categ_ids = [(5,)]
            reminder_date = False
            reminder_user_id = False

            real_rec = real_recs_map.get((record.res_model, record.res_id))
            if real_rec:
                tag_ids = [(6, 0, real_rec.technical_job_tag_ids.ids)]
                reminder_date = real_rec.reminder_date
                reminder_user_id = real_rec.reminder_user_id.id if real_rec.reminder_user_id else False
                html_data_src_doc = real_rec.get_job_data()
                technical_job_count = real_rec.technical_job_count
                show_technical_schedule_job_ids = [(6, 0, real_rec.show_technical_schedule_job_ids.ids)] if record.res_model != 'technical.job.schedule' else False
                date_field_name = record.config_id.date_field_id.name
                if date_field_name:
                    date_field_value = real_rec[date_field_name]
                    if date_field_value:
                        date_field_value = date_field_value + timedelta(days=1)
                estimated_visit_revenue = real_rec.estimated_visit_revenue
                job_duration = real_rec.job_duration

                is_schedule = record.res_model == 'technical.job.schedule'
                if not is_schedule:
                    next_job = real_rec.next_active_job_id
                    address = real_rec.address_label
                    if 'partner_id' in real_rec._fields and real_rec.partner_id:
                        partner = real_rec.partner_id
                        if partner.phone:
                            phones.append(partner.phone)
                        if partner.mobile:
                            phones.append(partner.mobile)
                        for part in partner.child_ids:
                            if part.phone:
                                phones.append(part.phone)
                            if part.mobile:
                                phones.append(part.mobile)
                    if 'phone' in real_rec._fields and real_rec.phone:
                        phones.append(real_rec.phone)
                    if 'mobile' in real_rec._fields and real_rec.mobile:
                        phones.append(real_rec.mobile)
                else:
                    next_job = real_rec

                internal_notes = real_rec.visit_internal_notes if not is_schedule else next_job.internal_notes
                internal_notes_html = internal_notes.replace("\n", "<br/>") if internal_notes else ""
                visit_payment_type = real_rec.visit_payment_type if not is_schedule else next_job.visit_payment_type
                visit_priority = real_rec.visit_priority if not is_schedule else next_job.visit_priority
                job_categ_ids = [(6, 0, (real_rec if not is_schedule else next_job).job_categ_ids.ids)]

                html = "<table style='border-collapse: collapse; border: none;'>"
                if is_schedule:
                    tj = tj_by_schedule.get(record.res_id)
                    link_id = tj.id if tj else record.res_id
                    link_model = 'technical.job' if tj else record.res_model
                    html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(link_id, link_model)
                else:
                    html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(record.res_id, record.res_model)
                html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(real_rec.display_name)

            record.internal_notes_html = internal_notes_html
            record.estimated_visit_revenue = estimated_visit_revenue
            record.address = address
            record.reminder_date = reminder_date
            record.reminder_user_id = reminder_user_id
            record.contact_number = '|'.join(phones) if phones else ""
            record.internal_notes = internal_notes
            record.job_duration = job_duration if not next_job else next_job.job_duration
            record.visit_payment_type = visit_payment_type
            record.visit_priority = visit_priority
            record.job_categ_ids = job_categ_ids
            record.technical_job_tag_ids = tag_ids
            record.date_field_value = date_field_value.date() if isinstance(date_field_value, datetime.datetime) else date_field_value
            record.technical_job_count = technical_job_count
            record.html_link_to_src_doc = html
            record.html_data_src_doc = html_data_src_doc
            record.next_active_job_id = next_job.id if next_job else False
            record.show_technical_schedule_job_ids = show_technical_schedule_job_ids if show_technical_schedule_job_ids else False

    def open_mail_compose_message_wiz(self):
        self.ensure_one()
        real_rec = self.env[self.res_model].browse(self.res_id)
        if real_rec:
            if 'message_ids' not in real_rec._fields.keys():
                raise ValidationError('El registro origen no tiene habilitadas las funciones de mensajeria')
            else:
                ctx = {
                    'default_model': self.res_model,
                    'default_res_id': self.res_id,
                    'default_whatsapp': True,
                }
                return {
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'res_model': 'mail.compose.message',
                    'views': [(False, 'form')],
                    'view_id': False,
                    'target': 'new',
                    'context': ctx,
                }
        else:
            raise ValidationError('No se ha podido encontrar el registro origen')

    address = fields.Char(compute=related_rec_fields, store=True, string="Direccion")
    contact_number = fields.Char(compute=related_rec_fields, store=True, string="N° Telefono")
    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=related_rec_fields, store=True, string="Operaciones")
    technical_job_tag_ids = fields.Many2many(comodel_name='technical.job.tag', compute=related_rec_fields, store=True, string="Etiquetas")
    reminder_date = fields.Date(compute=related_rec_fields, store=True, string="A Recordar")
    reminder_user_id = fields.Many2one('res.users', compute=related_rec_fields, store=True, string="Usuario Recordatorio")
    estimated_visit_revenue = fields.Float(compute=related_rec_fields, store=True, string="Estimado (EUR)")
    job_duration = fields.Float(compute=related_rec_fields, store=True, string="Horas estimadas")
    internal_notes = fields.Text(compute=related_rec_fields, store=True, string="Notas internas")
    internal_notes_html = fields.Html(compute=related_rec_fields, store=True, string="Notas int")
    visit_payment_type = fields.Selection(compute=related_rec_fields, store=True, string="Política de cobro", selection=[('free','Sin cargo'), ('to_bill','Con cargo')])
    visit_priority = fields.Selection(compute=related_rec_fields, store=True, string="Prioridad Visita",  selection=[('0', 'Sin definir'), ('1','Baja'), ('2','Media'), ('3','Alta')])
    job_categ_ids = fields.Many2many('technical.job.categ',compute=related_rec_fields, store=True, string="Categoria")
    next_active_job_id = fields.Many2one('technical.job.schedule', compute=related_rec_fields, store=True, string= "Próx. Planificación", ondelete='SET NULL')
    next_active_job_date = fields.Datetime(string="Fecha próx. planificación", related='next_active_job_id.date_schedule', store=True)
    @api.depends('next_active_job_id', 'next_active_job_id.date_schedule')
    def compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            res = False
            if record.next_active_job_id:
                if today > record.next_active_job_id.date_schedule.date():
                    res = True
            record.next_active_job_overdue = res
    next_active_job_overdue = fields.Boolean(string="Proximo Trabajo Vencido", compute=compute_is_overdue, store=True)
    date_field_value = fields.Datetime(string="Fecha interés")
    date_field_tag = fields.Char(string="Solicitud", related="config_id.date_field_tag")
    html_link_to_src_doc = fields.Html(compute=related_rec_fields, store=True, string="Documento origen")
    html_data_src_doc = fields.Html(compute=related_rec_fields, store=True, string="Info trabajo a realizar")
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
            next_job = False
            if record.res_model and record.res_id:
                real_rec = self.env[record.res_model].browse(record.res_id)
                if real_rec:
                    next_job = record.next_active_job_id if record.res_model != 'technical.job.schedule' else real_rec
                    technical_job = record.config_id.technical_job_type_id.id if record.config_id and record.config_id.technical_job_type_id else False
                    if record.res_model == 'technical.job.schedule':
                        job_status = next_job.job_status
                    elif technical_job:
                        if record.res_id and record.res_model == 'crm.lead' and \
                                not real_rec.show_technical_schedule_job_ids and \
                                real_rec.customer_availability_type in ('hour_range', 'week_availability', 'urgent'):
                            job_status = 'waiting_job'
                        elif next_job and next_job.job_type_id and next_job.job_type_id.id == technical_job:
                            job_status = next_job.job_status
                        else:
                            jobs = real_rec.show_technical_schedule_job_ids.filtered(lambda
                                                                                         x: x.job_type_id and x.job_type_id.id == technical_job and x.job_status != 'cancel' and x.job_status != 'done')
                            if jobs:
                                job_status = sorted(jobs, key=lambda r: r.date_schedule, reverse=True)[0].job_status
                        if record.res_model == 'technical.job.schedule':
                            job_status = next_job.job_status

            record.job_status = job_status


    job_status = fields.Selection([('no_job','Sin planificaciones'),
                                   ('waiting_job', 'Esperando confirmación'),
                                   ('to_do', 'Planificado'),
                                   ('confirmed', 'Confirmado'),
                                   ('stand_by', 'Aplazado'),
                                   ('done', 'Terminado'),
                                   ], store=True, compute=compute_assistant_status, string="Estado")


