from odoo import fields, models, api
import json
from odoo.exceptions import UserError, ValidationError


class TechnicalJobNoteAssistant(models.TransientModel):
    _name = "technical.job.note.assistant"

    new_opportunities = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Potencial otros trabajos")
    opportunities_description = fields.Text(string="Descripción oportunidad")
    opportunities_job_categ_id = fields.Many2one('technical.job.categ', string="Tipo oportunidad")

    currency_id = fields.Many2one('res.currency')
    content_type = fields.Char()
    pending_jobs = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Trabajos pendientes")
    needs_billing = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Necesita facturacion adicional?")
    material_cost = fields.Float(string="Gasto materiales")

    @api.depends('material_cost')
    def compute_material_price(self):
        for record in self:
            res = 0
            company = self.env.user.company_id
            res = record.material_cost*(company.material_rentability_multiplier or 1)
            record.material_final_price = res
    material_final_price = fields.Float(string="Precio final materiales", compute=compute_material_price)


    @api.depends('technical_job_id')
    def compute_time_to_bill(self):
        for record in self:
            res = 0
            if record.technical_job_id and record.technical_job_id.time_register_ids:
                res = sum(record.technical_job_id.time_register_ids.filtered(lambda x: not x.displacement).mapped('total_min'))/60
            company = self.env.user.company_id
            billing_unit = company.min_billing_time_hs
            billing_relation_unit = res/billing_unit
            if billing_relation_unit - int(billing_relation_unit) == 0:
                record.rounded_time_to_bill = res
            else:
                record.rounded_time_to_bill = int(billing_relation_unit)*billing_unit + billing_unit
            record.hs_to_bill = res

    @api.onchange('hs_to_bill')
    def onchange_hs_to_bill(self):
        if self.hs_to_bill and not self.hs_bill :
            self.hs_bill = True

    hs_bill = fields.Boolean(string="Facturar tiempo en domicilio")
    hs_to_bill = fields.Float(string="Hs invertidas", compute=compute_time_to_bill)
    rounded_time_to_bill = fields.Float(string="Tiempo a facturar", compute=compute_time_to_bill)

    @api.onchange('displacement_product_ids')
    def onchange_displacement_product_ids(self):
        self.ensure_one()
        if len(self.displacement_product_ids.mapped('id')) > 1:
            raise UserError('Solo puede seleccionar un tipo de desplazamiento')

    displacement_product_ids = fields.Many2many('product.product')

    @api.depends('technical_job_id')
    def get_displacement_domain(self):
        for record in self:
            company = self.env.user.company_id
            res = [('id', 'in', company.displacement_product_ids.mapped('id'))]
            record.displacement_product_domain = json.dumps(res)
    displacement_product_domain = fields.Char(compute=get_displacement_domain)

    content = fields.Text(required=True, string="Comentarios")
    technical_job_id = fields.Many2one('technical.job')
    attch_ids = fields.Many2many('ir.attachment', string="Adjuntos")



    @api.model
    def default_get(self, fields):
        result = super(TechnicalJobNoteAssistant, self).default_get(fields)
        result['content_type'] = self.env.context.get("note_assistant_type", False)
        result['technical_job_id'] = self.env.context.get("technical_job", False)
        result['pending_jobs'] = 'yes' if self.env.context.get("stand_by", False) else 'no'
        result['currency_id'] = self.env.user.company_id.currency_id.id
        return result

    def action_done(self):
        if len(self.displacement_product_ids.mapped('id')) > 1:
            raise UserError('Solo puede seleccionar un tipo de desplazamiento')
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
            content = f"\n\n→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}"
            self.technical_job_id.internal_notes += content
        else:
            content = f"→ {content_label} | {fields.Datetime.now().strftime('%d-%m-%Y %H:%M')}\n{self.content}"
            self.technical_job_id.internal_notes = content
        if self.content_type == 'Finalizacion trabajo':
            if self.pending_jobs == 'yes':
                self.technical_job_id.stand_by()
            else:
                self.technical_job_id.mark_as_done()
        if self.needs_billing=='yes':
            real_rec = False
            existing_po = False

            if self.technical_job_id and self.technical_job_id.res_id and self.technical_job_id.res_model:
                real_rec = self.env[self.technical_job_id.res_model].browse(self.technical_job_id.res_id)
                if real_rec:
                    existing_po = real_rec.get_sale_order()
                    body = "Tiene facturacion para revisar: " + self.technical_job_id.job_type_id.name
                    real_rec.with_context(mail_create_nosubscribe=True).message_post(body=body, message_type='comment',
                                                                                    partner_ids=real_rec.user_id.mapped(
                                                                                        'partner_id.id'))
            company = self.env.user.company_id
            if not existing_po:
                lines = []
                if self.material_final_price:
                    lines.append((0, 0, self.prepare_material_cost_line()))
                if self.displacement_product_ids:
                    lines.append((0, 0, self.prepare_displacement_line()))
                if self.rounded_time_to_bill and self.hs_bill:
                    lines.append((0, 0, self.prepare_billing_time_line()))
                if lines:
                    so_vals = {
                        'order_line': lines,
                        'date_order': fields.Date.context_today(self),
                        #'warehouse': '',
                        'partner_id': real_rec.partner_id.id if real_rec else False,
                        'partner_invoice_id': real_rec.partner_id.id if real_rec else False,
                        'partner_shipping_id': real_rec.partner_id.id if real_rec else False,
                        'journal_id': company.default_job_billing_journal_id.id if company.default_job_billing_journal_id else False,
                        'opportunity_id': real_rec.id if real_rec._name == 'crm.lead' else False ,
                        'user_id': real_rec.user_id.id if real_rec and real_rec.user_id else self.env.user.id,
                        'team_id': real_rec.team_id.id if real_rec and 'team_id' in real_rec._fields.keys() and real_rec.team_id else False,
                        'require_signature': True,
                        'origin': self.technical_job_id.display_name,
                    }
                    existing_po = self.env['sale.order'].create(so_vals)
            else:
                lines = []
                if self.material_final_price:
                    lines.append((0, 0, self.prepare_material_cost_line()))
                if self.displacement_product_ids:
                    lines.append((0, 0, self.prepare_displacement_line()))
                if self.rounded_time_to_bill and self.hs_bill:
                    lines.append((0, 0, self.prepare_billing_time_line()))
                if lines:
                    so_write_vals = {
                        'order_line': lines,
                        'origin': existing_po.origin + " " + self.technical_job_id.display_name
                    }
                    existing_po.write(so_write_vals)
            if self.technical_job_id and self.technical_job_id.schedule_id:
                self.technical_job_id.schedule_id.sale_order_id = existing_po.id
        if self.new_opportunities=='yes':
            real_rec = False
            if self.technical_job_id and self.technical_job_id.res_id and self.technical_job_id.res_model:
                real_rec = self.env[self.technical_job_id.res_model].browse(self.technical_job_id.res_id)
            source = self.env['utm.source'].search([('name', '=', 'Trabajo en domicilio')])
            if not source:
                source = self.env['utm.source'].create({'name': 'Trabajo en domicilio'})
            lead_vals = {
                'type': 'lead',
                'name': f'{self.opportunities_job_categ_id.name} | {real_rec.partner_id.name if real_rec else ""}' ,
                'partner_id': real_rec.partner_id.id if real_rec else False,
                'type_of_client': real_rec.type_of_client if real_rec else False,
                'description': self.opportunities_description.replace('\n', '<br/>'),
                'source_id': source[0].id,
            }
            self.env['crm.lead'].create(lead_vals)

        return {'type': 'ir.actions.act_window_close'}

    def prepare_material_cost_line(self):
        company = self.env.user.company_id
        vals = {
            'product_id': company.material_product_id.id,
            'name': f'{company.material_product_id.name} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
            'product_uom_qty': 1,
            'price_unit': self.material_final_price,
        }
        return vals

    def prepare_displacement_line(self):
        vals = {
            'product_id': self.displacement_product_ids.mapped('id')[0],
            'name': f'{self.displacement_product_ids.mapped("name")[0]} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
            'product_uom_qty': 1,
        }
        return vals

    def prepare_billing_time_line(self):
        company = self.env.user.company_id
        vals = {
            'product_id': company.billing_time_product_id.id,
            'name': f'{company.billing_time_product_id.name} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
            'product_uom_qty': self.rounded_time_to_bill,
        }
        return vals


