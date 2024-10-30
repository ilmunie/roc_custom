
from odoo import fields, models, api, SUPERUSER_ID
from datetime import timedelta
from odoo.exceptions import UserError, ValidationError


class TechnicalJob(models.Model):
    _name = 'technical.job'
    _inherit = ['mail.thread']

    allow_displacement_tracking = fields.Boolean(related='job_type_id.allow_displacement_tracking')
    data_assistant = fields.Boolean(related='job_type_id.data_assistant')

    def edit_internal_note(self):
        self.ensure_one()
        action = {
            'name': "Edicion notas internas",
            'type': 'ir.actions.act_window',
            'view_id': self.env.ref('roc_custom.quick_data_edit_technical_job').id,
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': self.id,
            'res_model': 'technical.job',
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

    @api.depends('internal_notes')
    def related_internal_notes(self):
        for record in self:
            record.internal_notes_html = record.internal_notes.replace("\n", "<br/>") if record.internal_notes else ""
    internal_notes_html = fields.Html(compute=related_internal_notes, string="Notas int")



    @api.depends('job_employee_ids')
    def see_ass_button(self):
        for record in self:
            res = False
            employee = self.env.user.employee_id
            if employee:
                if employee.id not in record.job_employee_ids.mapped('id'):
                    res = True
            record.see_assign_button = res


    see_assign_button = fields.Boolean(compute=see_ass_button)

    def assign_to_me(self):
        self.job_employee_ids = [(4, self.env.user.employee_id.id)]

    time_register_ids = fields.One2many(related='schedule_id.time_register_ids')

    def open_checklist_wiz(self):
        ctx = {'technical_job': self.id}
        return {
            'name': "Checklist Operaciones",
            'res_model': 'technical.job.checklist.assistant',
            'type': 'ir.actions.act_window',
            'context': ctx,
            'target': 'new',
            "view_type": "form",
            "view_mode": "form",
        }
    checklist_line_ids = fields.One2many(related='schedule_id.checklist_line_ids')


    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("update_assistant_id", False):
            self.env['technical.job.assistant'].browse(self.env.context.get("update_assistant_id", False)).related_rec_fields()
        return res

    def open_form_partner(self):
        action = self.env.ref('roc_custom.action_technical_job_partner_form').read()[0]
        if self.res_model == 'crm.lead':
            real_rec = self.env[self.res_model].browse(self.res_id)
            if real_rec.partner_id:
                action["res_id"] = real_rec.id
            else:
                UserWarning('No hay una cliente asociado al registro')
        else:
            UserWarning('No hay una configuración de Cliente Definida')
        return action

    def open_sale_order_wiz(self):
        self.ensure_one()
        if self.res_model == 'crm.lead':
            opportunity = self.env[self.res_model].browse(self.res_id)
            action = {
                        'name': "Venta",
                        'res_model': 'sale.order',
                        'type': 'ir.actions.act_window',
                        'views': [(self.env.ref('roc_custom.technical_job_sale_order').id, 'form')],
                        'context': {'default_partner_id': opportunity.partner_id.id if opportunity.partner_id else False,
                                    'default_journal_id': 26,
                                    'default_opportunity_id': self.res_id},
                        'mode': 'new'
                    }
            if opportunity.order_ids:
                action['res_id'] = opportunity.order_ids[0].id
                sale_order = opportunity.order_ids[0]
                if sale_order.sale_order_template_id.technical_job_template and any(line.technical_job_duration for line in
                                                                              sale_order.sale_order_template_id.sale_order_template_line_ids):
                    time_prod = sale_order.sale_order_template_id.sale_order_template_line_ids.filtered(
                        lambda x: x.technical_job_duration).mapped('product_id.id')
                    lines_to_update = sale_order.order_line.filtered(lambda x: x.product_id.id in time_prod)
                    if sale_order.opportunity_id and sale_order.opportunity_id.total_job_minutes:
                        lines_to_update.product_uom_qty = sale_order.opportunity_id.total_job_minutes / 60
            return action

    def menu_to_calendar(self):
        action = self.env.ref('roc_custom.action_technical_job').read()[0]
        user_type = 'planner' if self.env.user.has_group('roc_custom.technical_job_planner') else 'user'
        if user_type == 'user':
            context = {
                'search_default_myjobs': 1,
                'search_default_active': 1,
                'default_mode': "week" if self.env.user.has_group('roc_custom.technical_job_planner') else "day"}
            action['context'] = context
        return action
    #

    @api.onchange('res_id')
    def _onchange_res_id(self):
        for record in self:
            if record.res_id and record.res_model:
                real_rec = self.env[self.res_model].browse(self.res_id)
                if real_rec.job_employee_ids:
                    record.job_employee_ids = [(6, 0, real_rec.job_employee_ids.mapped('id'))]
                if real_rec.job_vehicle_ids:
                    record.job_vehicle_ids = [(6, 0, real_rec.job_vehicle_ids.mapped('id'))]
                if real_rec.technical_job_tag_ids:
                    record.technical_job_tag_ids = [(6, 0, real_rec.technical_job_tag_ids.mapped('id'))]
                if real_rec.job_duration:
                    record.job_duration = real_rec.job_duration
                if real_rec.visit_internal_notes:
                    record.internal_notes = real_rec.visit_internal_notes
                if real_rec.visit_payment_type:
                    record.visit_payment_type = real_rec.visit_payment_type
                if real_rec.visit_priority:
                    record.visit_priority = real_rec.visit_priority
                if real_rec.job_categ_ids:
                    record.job_categ_ids = [(6, 0, real_rec.job_categ_ids.mapped('id'))]
                if real_rec.estimated_visit_revenue:
                    record.estimated_visit_revenue = real_rec.estimated_visit_revenue


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
            if record.start_tracking_time and record.schedule_id:
                record.schedule_id.stop_tracking()
            if record.displacement_start_datetime:
                record.end_displacement()
            if not record.internal_notes:
                raise ValidationError("Debe ingresar una nota interna para aplazar la operacion")
            jobs_edit = []
            jobs_edit.append(record)
            if record.schedule_id:
                jobs_edit.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_edit:
                job.write({'job_status': 'stand_by'})
            if record.res_id and record.res_model:
                rec = self.env[record.res_model].browse(record.res_id)
                body = "Ha aplazado la operación " + record.job_type_id.name
                rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment')


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
            if record.start_tracking_time and record.schedule_id:
                record.schedule_id.stop_tracking()
            if record.displacement_start_datetime:
                record.end_displacement()
            user_type = 'planner' if self.env.user.has_group('roc_custom.technical_job_planner') else 'user'
            if record.job_type_id.requires_documentation and record.res_id and not record.attch_ids and user_type=='user':
                raise ValidationError('Cargue la documentación correspondiente')
            if record.job_type_id.force_time_registration and user_type=='user' and not record.minutes_in_job:
                raise ValidationError('Debe registrar tiempo en la operacion')
            jobs_to_make_done = []
            jobs_to_make_done.append(record)
            if record.schedule_id:
                jobs_to_make_done.extend(
                    self.env['technical.job'].search([('schedule_id', '=', record.schedule_id.id)]))
            for job in jobs_to_make_done:
                job.write({'job_status': 'done'})

            if (record.res_id and record.res_model):
                body = "Ha finalizado la operación: " + record.job_type_id.name
                if record.minutes_in_job:
                    body += f"<br/> TIEMPO TOTAL REGISTRADO: {round(record.minutes_in_job, 0)} min"
                    body += f"<br/> LLEGADA: {record.arrive_time} | SALIDA: {record.out_time}"
                rec = self.env[record.res_model].browse(record.res_id)
                rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment',
                                                                            partner_ids=rec.user_id.mapped(
                                                                                'partner_id.id'))
                rec = self.env[record.res_model].browse(record.res_id)
                model_configs = self.env['technical.job.assistant.config'].search([('model_id.model', '=', rec._name)])
                config = False
                for model_conf in model_configs:
                    domain = eval(model_conf.domain_condition)
                    domain.insert(0, ('id', '=', rec.id))
                    if self.env[rec._name].search_count(domain) > 0:
                        config = model_conf
                        break
                if config:
                    for wr_action in config.action_done_line_ids:
                        apply = True
                        if wr_action.wiz_condition:
                            wizard = self.env.context.get('wiz_id', False)
                            domain = eval(wr_action.wiz_condition)
                            domain.insert(0, ('id', '=', wizard.id))
                            if wizard and not self.env[wizard._name].search(domain):
                                apply = False
                        if wr_action.domain_condition:
                            domain = eval(wr_action.domain_condition)
                            domain.insert(0, ('id', '=', rec.id))
                            if not self.env[rec._name].search(domain):
                                apply = False
                        if apply:
                            rec.write(eval(wr_action.write_vals))
                if rec.manual_technical_job:
                    rec.manual_technical_job = False
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
            if self.env.context.get("update_assistant_id", False):
                self.delete_schedule_tree()
                assistant =  self.env['technical.job.assistant'].browse(
                    self.env.context.get("update_assistant_id", False))
                if assistant.res_model == 'technical.job.schedule':
                    assistant.unlink()
                else:
                    assistant.related_rec_fields()
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

            else:
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
            if rec.technical_job_tag_ids:
                name += ' - '.join(rec.technical_job_tag_ids.mapped('name'))
            if rec.job_status:
                if name:
                    name += " | "
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
            res.append((rec.id, name))
        return res

    def get_schedule_attch(self):
        for record in self:
            res_model = 'technical.job.schedule' if not record.schedule_id.res_model else record.schedule_id.res_model
            res_id = record.schedule_id.id if not record.schedule_id.res_model else record.schedule_id.res_id
            att = self.env['ir.attachment'].search([('res_id','=', res_id),('res_model', '=', res_model), ('added_from_technical_job', '=', True)])
            record.attch_ids = [(6, 0, att.mapped('id'))]

    attch_ids = fields.Many2many('ir.attachment', compute=get_schedule_attch)
    technical_job_tag_ids = fields.Many2many(related="schedule_id.technical_job_tag_ids", readonly=False)
    visit_priority = fields.Selection(related="schedule_id.visit_priority", readonly=False, store=True, force_save=True)
    job_categ_ids = fields.Many2many(related="schedule_id.job_categ_ids", readonly=False)
    datetime_in_status = fields.Datetime(related="schedule_id.datetime_in_status", store=True)

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

    sale_order_ids = fields.Many2many(related="schedule_id.sale_order_ids")
    visit_payment_type = fields.Selection(related="schedule_id.visit_payment_type", readonly=False, store=True, force_save=True)
    estimated_visit_revenue = fields.Float(related="schedule_id.estimated_visit_revenue", readonly=False, store=True, force_save=True)
    displacement_total_min = fields.Float(related="schedule_id.displacement_total_min")
    billable_total_min = fields.Float(related="schedule_id.billable_total_min")

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

    minutes_in_job = fields.Float(related='schedule_id.minutes_in_job', force_save=True, readonly=False)
    arrive_time = fields.Datetime(related='schedule_id.arrive_time', force_save=True, readonly=False)
    out_time = fields.Datetime(related='schedule_id.out_time', force_save=True, readonly=False)
    start_tracking_time = fields.Datetime(related='schedule_id.start_tracking_time', force_save=True)

    #function for displacement register in schedule_id

    displacement_start_datetime = fields.Datetime(related='schedule_id.displacement_start_datetime')

    def start_displacement(self):
        self.ensure_one()
        schedule_id = self.schedule_id
        if schedule_id:
            schedule_id.time_register_ids = [(0, 0, {'start_time': fields.Datetime.now(), 'displacement': True})]
            schedule_id.displacement_start_datetime = fields.Datetime.now()

    def end_displacement(self):
        self.ensure_one()
        schedule_id = self.schedule_id
        if schedule_id:
            register_to_end = schedule_id.time_register_ids.filtered(lambda x: x.displacement and not x.end_time)
            for reg in register_to_end:
                reg.end_time = fields.Datetime.now()
            schedule_id.displacement_start_datetime = False

    def call_billing_wiz(self):
        ctx = {'technical_job': self.id}
        return {
            'name': "Facturacion trabajo",
            'res_model': 'technical.job.billing.assistant',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': ctx,
            'target': 'current',
        }


    def call_checkout_wiz(self):
        ctx = {'note_assistant_type': 'Finalizacion trabajo', 'technical_job': self.id}
        return {
            'name': "Finalizacion trabajo",
            'res_model': 'technical.job.note.assistant',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': ctx,
            'target': 'new',
        }
    def call_checkout_wiz_standby(self):
        ctx = {'note_assistant_type': 'Finalizacion trabajo', 'technical_job': self.id, 'stand_by':True}
        return {
            'name': "Aplazar trabajo",
            'res_model': 'technical.job.note.assistant',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'context': ctx,
            'target': 'new',
        }



    # functions to track time in job
    def stop_tracking(self):
        if self.schedule_id:
            self.schedule_id.stop_tracking()
            self.schedule_id.out_time = fields.Datetime.now()
            if self.job_type_id.data_assistant:
                ctx = {'note_assistant_type': 'Finalizacion trabajo', 'technical_job': self.id}
                return {
                    'name': "Descripción trabajo realizado",
                    'res_model': 'technical.job.note.assistant',
                    'type': 'ir.actions.act_window',
                    'view_mode': 'form',
                    'context': ctx,
                    'target': 'new',
                }
            else:
                self.mark_as_done()


    def start_tracking(self):
        if self.schedule_id:
            self.schedule_id.start_tracking()
            if not self.schedule_id.arrive_time:
                self.schedule_id.arrive_time = fields.Datetime.now()
        if self.job_type_id.data_assistant:
            ctx = {'note_assistant_type': 'Descripcion Inicial', 'technical_job': self.id}
            return {
                'name': "Descripción antes de realizar el trabajo",
                'res_model': 'technical.job.note.assistant',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'context': ctx,
                'target': 'new',
            }

    @api.depends('date_schedule', 'job_duration')
    def get_end_time(self):
        for record in self:
            record.end_time = record.date_schedule + timedelta(hours=record.job_duration) if record.date_schedule else False
    end_time = fields.Datetime(compute=get_end_time, store=True)



class IrAtt(models.Model):
    _inherit = 'ir.attachment'

    added_from_technical_job = fields.Boolean()
    
    @api.model
    def check(self, mode, values=None):
        return True


    @api.model_create_multi
    def create(self, vals_list):
        new_val_list = []
        for val in vals_list:
            if 'res_model' in val.keys() and val['res_model'] == 'technical.job':
                schedule = self.env['technical.job'].browse(val['res_id']).schedule_id
                model = 'technical.job.schedule' if not schedule.res_model else schedule.res_model
                res_id = schedule.id if not schedule.res_model else schedule.res_id
                val['res_model'] = model
                val['res_id'] = res_id
                val['added_from_technical_job'] = True
                new_val_list.append(val)
            else:
                new_val_list.append(val)
        records = super().create(new_val_list)
        return records