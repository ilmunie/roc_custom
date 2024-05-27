from odoo import fields, models, api, SUPERUSER_ID

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


class TechnicalJobAssistant(models.TransientModel):
    _name = 'technical.job.assistant'

    def see_src_document(self):
        self.ensure_one()
        if self.res_id and self.res_model:
            action = {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': self.res_model,
                'target': 'current',
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
        for config in configs:
            domain_to_check = eval(config.domain_condition) if config.domain_condition else []
            matching_records = self.env[config.model_id.model].search(domain_to_check)
            recs_to_create.extend([{'res_model': rec._name, 'res_id': rec.id, 'config_id': config.id} for rec in matching_records])
        self.env['technical.job.assistant'].create(recs_to_create)
        return {
            'name': "Planificación de Operaciones",
            'res_model': 'technical.job.assistant',
            'type': 'ir.actions.act_window',
            'context': {'search_default_assigned_to_me': 1, 'search_default_configuration': 1, 'search_default_job_status': 1,},
            'domain': [('create_uid','=',self.env.user.id)],
            'views': [(self.env.ref('roc_custom.technical_job_assistant_tree_view').id, 'tree')],
        }

    res_model = fields.Char(string="Modelo")
    res_id = fields.Integer(string="ID")
    @api.depends('res_model','res_id')
    def related_rec_fields(self):
        for record in self:
            show_technical_schedule_job_ids = []
            html = ""
            job_status = 'no_job'
            next_job = False
            technical_job_count = 0
            date_field_value = False
            if record.res_model and record.res_id:
                real_rec = self.env[record.res_model].browse(record.res_id)
                if real_rec:
                    technical_job_count = real_rec.technical_job_count
                    show_technical_schedule_job_ids = [(6,0,real_rec.show_technical_schedule_job_ids.mapped('id'))]
                    date_field_value = real_rec[record.config_id.date_field_id.name]
                    next_job = real_rec.next_active_job_id
                    html += "<table style='border-collapse: collapse; border: none;'>"
                    html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(
                        record.res_id,
                        record.res_model)
                    html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(real_rec.display_name)
                    technical_job = record.config_id.technical_job_type_id.id if record.config_id and record.config_id.technical_job_type_id else False
                    if technical_job:
                        if next_job and next_job.job_type_id and next_job.job_type_id.id == technical_job:
                            job_status = next_job.job_status
                        else:
                            jobs = real_rec.show_technical_schedule_job_ids.filtered(lambda x: x.job_type_id and x.job_type_id.id == technical_job and x.job_status != 'cancel')
                            if jobs:
                                job_status = sorted(jobs, key=lambda r: r.date_schedule, reverse=True)[0].job_status

            record.date_field_value = date_field_value
            record.technical_job_count = technical_job_count
            record.html_link_to_src_doc = html
            record.job_status = job_status
            record.next_active_job_id = next_job.id if next_job else False
            record.next_active_job_date = next_job.date_schedule if next_job else False
            record.next_active_job_type_id = next_job.job_type_id.id if next_job and next_job.job_type_id else False
            record.next_job_employee_ids = [(6,0,next_job.job_employee_ids.mapped('id'))] if next_job else False
            record.next_job_vehicle_ids = [(6,0,next_job.job_vehicle_ids.mapped('id'))] if next_job else False
            record.show_technical_schedule_job_ids = show_technical_schedule_job_ids if show_technical_schedule_job_ids else False

    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=related_rec_fields, store=True, string="Operaciones")
    next_active_job_id = fields.Many2one('technical.job.schedule', compute=related_rec_fields, store=True, string= "Próx. Planificación")
    next_active_job_date = fields.Date(string="Fecha próx. planificación")
    date_field_value = fields.Datetime(string="Fecha interés")
    date_field_tag = fields.Char(string="Solicitud", related="config_id.date_field_tag")
    html_link_to_src_doc = fields.Html(compute=related_rec_fields, store=True, string="Documento origen")
    technical_job_count = fields.Integer(string='Planificaciones activas')
    next_active_job_type_id = fields.Many2one('technical.job.type', string="Tipo próx. trabajo")
    next_job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")
    next_job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita")
    job_status = fields.Selection([('no_job','Sin planificaciones'),
                                   ('to_do', 'Planificado'),
                                   ('stand_by', 'Stand By'),
                                   ('done', 'Terminado'),
                                   ], store=True, compute=related_rec_fields, string="Estado")