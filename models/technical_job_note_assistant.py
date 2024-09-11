from odoo import fields, models, api
import json
from odoo.exceptions import UserError, ValidationError


class TechnicalJobNoteAssistant(models.TransientModel):
    _name = "technical.job.note.assistant"

    new_opportunities = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], string="Potencial otros trabajos")
    opportunities_description = fields.Text(string="Descripción oportunidad")
    opportunities_job_categ_ids = fields.Many2many('technical.job.categ', string="Tipo oportunidad")
    opp_attch_ids = fields.Many2many('ir.attachment','technical_job_opp_creation_att_rel', 'wiz_id', 'attach_id', string="Adjuntos")

    currency_id = fields.Many2one('res.currency')
    content_type = fields.Char()
    pending_jobs = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], string="Trabajos pendientes")
    needs_billing = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], string="Necesita facturacion adicional?")
    content = fields.Text(required=True, string="Comentarios")
    todo_description = fields.Text(string="A realizar")
    technical_job_id = fields.Many2one('technical.job')
    attch_ids = fields.Many2many('ir.attachment', string="Adjuntos")



    @api.model
    def default_get(self, fields):
        result = super(TechnicalJobNoteAssistant, self).default_get(fields)
        result['content_type'] = self.env.context.get("note_assistant_type", False)
        result['technical_job_id'] = self.env.context.get("technical_job", False)
        #result['pending_jobs'] = 'yes' if self.env.context.get("stand_by", False) else 'no'
        result['currency_id'] = self.env.user.company_id.currency_id.id
        return result

    def action_done(self):
        if len(self.attch_ids) == 0:
            raise UserError('Debe agregar al menos una foto adjunta')
        else:
            att_vals = []
            for att in self.attch_ids:
                att_vals.append((4, att.id))
            self.technical_job_id.attch_ids = att_vals
        if self.content_type == 'Finalizacion trabajo' and self.pending_jobs == 'yes':
            content_label = 'Pendientes'
        else:
            content_label = self.content_type

        if self.technical_job_id.internal_notes:
            if self.content_type == 'Descripcion Inicial':
                content = f"\n\n→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}\n\n→A realizar\n{self.todo_description}"
            else:
                content = f"\n\n→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}"
            self.technical_job_id.internal_notes += content
        else:
            if self.content_type == 'Descripcion Inicial':
                content = f"→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}\n\n→A realizar\n{self.todo_description}"
            else:
                content = f"→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}"
            self.technical_job_id.internal_notes = content
        if self.content_type == 'Finalizacion trabajo':
            if self.pending_jobs == 'yes':
                self.technical_job_id.stand_by()
            else:
                self.technical_job_id.mark_as_done()
        if self.new_opportunities=='yes':
            real_rec = False
            if self.technical_job_id and self.technical_job_id.res_id and self.technical_job_id.res_model:
                real_rec = self.env[self.technical_job_id.res_model].browse(self.technical_job_id.res_id)
            source = self.env['utm.source'].search([('name', '=', 'Trabajo en domicilio')])
            if not source:
                source = self.env['utm.source'].create({'name': 'Trabajo en domicilio'})
            lead_vals = {
                'type': 'lead',
                'name': f"{','.join(self.opportunities_job_categ_ids.mapped('name'))} | {real_rec.partner_id.name if real_rec else ''}" ,
                'partner_id': real_rec.partner_id.id if real_rec else False,
                'type_of_client': real_rec.type_of_client if real_rec else False,
                'description': self.opportunities_description.replace('\n', '<br/>'),
                'source_id': source[0].id,
                'job_categ_ids': [(6, 0, self.opportunities_job_categ_ids.mapped('id'))],
            }
            new_lead = self.env['crm.lead'].create(lead_vals)
            if self.opp_attch_ids:
                new_lead.with_context(mail_create_nosubscribe=True).message_post(body="Ha agregado archivos adjuntos", message_type='comment',
                                                                                 attachment_ids=self.opp_attch_ids.mapped('id'))
        if self.needs_billing == 'yes' and self.content_type == 'Finalizacion trabajo':
            ctx = {'technical_job': self.technical_job_id.id}
            return {
                'name': "Facturacion trabajo",
                'res_model': 'technical.job.billing.assistant',
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'context': ctx,
                'target': 'new',
            }
        else:
            return {'type': 'ir.actions.act_window_close'}



