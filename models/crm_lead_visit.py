from odoo import fields, models, api, SUPERUSER_ID

class CrmLeadVisit(models.Model):
    _name = 'crm.lead.visit'

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            name = ''
            if rec.visit_user_id:
                name = rec.visit_user_id.display_name + " | "
            if rec.visit_vehicle:
                name += rec.visit_vehicle.display_name + "     |     "
            name += rec.lead_id.display_name + ' (' + rec.visit_status + ' | ' + rec.lead_id.stage_id.display_name + ')'
            res.append((rec.id, name))
        return res

    lead_id = fields.Many2one('crm.lead', readonly="1", force_save="1")
    tag_ids = fields.Many2many(related="lead_id.tag_ids", string="Etiquetas", readonly=False)
    visit_user_ids = fields.Many2many(related="lead_id.visit_user_ids", readonly=False, string="Personal visita")
    intrest_tag_ids = fields.Many2many(related="lead_id.intrest_tag_ids", string="Productos de Interés")
    lead_stage_id = fields.Many2one(related="lead_id.stage_id", string="Etapa")
    lead_team_id = fields.Many2one(related="lead_id.team_id", string="Equipo de ventas")
    visit_user_id = fields.Many2one('res.users', readonly="1", force_save="1", string="Asignado")
    visit_vehicle = fields.Many2one(related='lead_id.visit_vehicle',store=True, readonly=False, string="Vehículo")
    partner_id = fields.Many2one(related='lead_id.partner_id', string="Cliente")
    calendar_date = fields.Datetime(related='lead_id.calendar_date', string="Fecha visita")
    date_schedule_visit = fields.Datetime(related='lead_id.date_schedule_visit' ,store=True, readonly=False, string="Fecha a visitar")
    user_id = fields.Many2one(related='lead_id.user_id',store=True, string="Comercial")
    visit_duration = fields.Float(related='lead_id.visit_duration', store=True, readonly=False, string="Tiempo visita (hs.)")
    visited = fields.Boolean(related='lead_id.visited', store=True, readonly=False, string="Visita terminada")
    visit_status = fields.Char(related='lead_id.visit_status', string="Estado visita")
    date_visited = fields.Datetime(related='lead_id.date_visited', store=True, string="Visitado el")





