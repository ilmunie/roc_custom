from odoo import fields, models, api, SUPERUSER_ID

class TechnicalJobType(models.Model):
    _name = 'technical.job.type'

    name = fields.Char(string="Name")
    default_duration_hs = fields.Float(string="Duración Hs")

class TechnicalJobSchedule(models.Model):
    _name = 'technical.job.schedule'

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

    def get_html_link_to_src_doc(self):
        for record in self:
            html = ""
            html += "<table style='border-collapse: collapse; border: none;'>"
            html += "<tr><td style='border: none;'><a href='/web#id={}&view_type=form&model={}' target='_blank'>".format(
                record.res_id,
                record.res_model)
            html += "<i class='fa fa-arrow-right'></i> {}</a></td></tr>".format(record.source_document_display_name)
            record.html_link_to_src_doc = html

    html_link_to_src_doc = fields.Html(compute=get_html_link_to_src_doc, string="Doc. Origen")
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
    @api.onchange('job_type_id')
    def _onchange_job_type_id(self):
        for record in self:
            if record.job_type_id:
                record.job_duration = record.job_type_id.default_duration_hs

    job_type_id = fields.Many2one('technical.job.type', string="Tipo trabajo")
    res_model = fields.Char()
    res_id = fields.Integer()
    job_employee_ids = fields.Many2many(comodel_name='hr.employee', string="Personal visita")
    job_vehicle_ids = fields.Many2many('fleet.vehicle', string="Vehículo")
    date_schedule = fields.Datetime(string="Fecha a visitar")
    user_id = fields.Many2one('res.users', store=True, string="Responsable")
    job_duration = fields.Float(string="Tiempo visita (hs.)")
    job_status = fields.Selection(
        selection=[('to_do', 'Planificado'), ('stand_by', 'Stand By'), ('done', 'Terminado'), ('cancel', 'Cancelado')],
        string="Estado", default='to_do')

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
            for employee in rec.job_employee_ids:
                for vehicle in rec.job_vehicle_ids:
                    self.env['technical.job'].create({
                        'job_employee_id': employee.id,
                        'job_vehicle_id': vehicle.id,
                        'schedule_id': rec.id
                                            })
            rec.trigger_refresh_jobs = False if rec.trigger_refresh_jobs else False


class TechnicalJob(models.Model):
    _name = 'technical.job'

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


    html_data_src_doc = fields.Html(related='schedule_id.html_data_src_doc', readonly=False, force_sale=True)
    html_link_to_src_doc = fields.Html(related='schedule_id.html_link_to_src_doc', readonly=False, force_sale=True)
    source_document_display_name = fields.Char(related='schedule_id.source_document_display_name', readonly=False, force_sale=True)
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
    job_status = fields.Selection(related="schedule_id.job_status", force_save=True, readonly=False, store=True )
    job_employee_ids = fields.Many2many(related='schedule_id.job_employee_ids', force_save=True, readonly=False )
    job_vehicle_ids = fields.Many2many(related='schedule_id.job_vehicle_ids', force_save=True, readonly=False)


class TechnicalJobMixin(models.AbstractModel):
    _name = 'technical.job.mixing'

    def get_job_data(self):
        return False

    technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule')
    def show_technical_jobs(self):
        for record in self:
            record.show_technical_schedule_job_ids = [(6,0,record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule).mapped('id'))]

    show_technical_schedule_job_ids = fields.Many2many(comodel_name='technical.job.schedule', compute=show_technical_jobs, string="Trabajos técnicos")
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
    @api.depends('technical_schedule_job_ids','technical_schedule_job_ids.job_status','technical_schedule_job_ids.date_schedule')
    def get_next_job(self):
        for record in self:
            res = False
            active_jobs = sorted(record.technical_schedule_job_ids.filtered(lambda x: x.date_schedule and x.job_status not in ('done', 'cancel')), key=lambda x: x.date_schedule)
            if active_jobs:
                res = active_jobs[0].id
            record.next_active_job_id = res

    next_active_job_id = fields.Many2one('technical.job.schedule', compute=get_next_job, store=True)

    def action_schedule_job(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("roc_custom.action_technical_job")
        self.write({'technical_schedule_job_ids': [(0, 0, {'res_model': self._name, 'res_id': self.id})]})
        action['context'] = {
            'default_schedule_id': self.technical_schedule_job_ids.filtered(lambda x: not x.date_schedule)[0].id,
            'default_res_id': self.id,
            'default_res_model': self._name,
            'default_mode': "week",
            'initial_date': False,
        }
        #import pdb;pdb.set_trace()
        return action

class CrmLead(models.Model,TechnicalJobMixin):
    _inherit = 'crm.lead'

    def get_job_data(self):
        return self.address_label

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