from odoo import fields, models, api
import json
from odoo.exceptions import UserError, ValidationError

class TechnicalJobNoteAssistantLine(models.TransientModel):
    _name = "technical.job.note.assistant.line"

    wiz_id = fields.Many2one('technical.job.note.assistant')
    product_template_id = fields.Many2one('product.template', string="Producto")
    attr_readonly = fields.Boolean()
    product_price = fields.Float(string="Precio", related='product_id.lst_price')
    currency_id = fields.Many2one(related='wiz_id.currency_id')


    @api.depends('product_template_id', 'attr_value_ids')
    def compute_attr_value_domain(self):
        for record in self:
            res = [('id', 'in', record.product_template_id.mapped('product_variant_ids').mapped('product_template_variant_value_ids.product_attribute_value_id.id'))]
            if record.attr_value_ids:
                res.append(('attribute_id.id', 'not in', record.attr_value_ids.mapped('attribute_id.id')))
            if not res:
                res = [('id', '=', 1)]
            record.attr_value_domain = json.dumps(res)

    attr_value_domain = fields.Char(compute=compute_attr_value_domain)
    attr_value_ids = fields.Many2many('product.attribute.value', string="Personalizaciones")

    @api.onchange('product_domain')
    def onchange_attr_values(self):
        if not self.product_id:
            matching_products = self.env['product.product'].search(json.loads(self.product_domain))
            if len(matching_products) == 1:
                self.product_id = matching_products[0].id

    product_id = fields.Many2one('product.product')
    @api.depends('attr_value_ids', 'product_template_id')
    def get_product_domain(self):
        for record in self:
            res = [('product_tmpl_id', '=', record.product_template_id.id)]
            if record.attr_value_ids:
                for att_value in record.attr_value_ids:
                    res.append(('product_template_variant_value_ids.product_attribute_value_id.name', '=', att_value.name))
            record.product_domain = json.dumps(res)
    product_domain = fields.Char(compute=get_product_domain)


class TechnicalJobNoteAssistant(models.TransientModel):
    _name = "technical.job.note.assistant"

    @api.onchange('technical_job_template_id')
    def onchange_technical_job_template_id(self):
        self.ensure_one()
        vals = [(5,)]
        for line in self.technical_job_template_id.line_ids:
            if len(line.product_tmpl_id.mapped('product_variant_ids')) <= 1:
                vals.append((0, 0,
                             {'product_template_id': line.product_tmpl_id.id,
                              'attr_readonly': True,
                              'attr_value_ids': [(6, 0, line.default_attr_value_ids.mapped('id'))],
                              'product_id': line.product_tmpl_id.product_variant_ids[0].id}))
            else:
                vals.append((0, 0,
                             {'product_template_id': line.product_tmpl_id.id,
                              'attr_value_ids': [(6, 0, line.default_attr_value_ids.mapped('id'))]}))
        self.line_ids = vals
        for line in self.line_ids:
            line.onchange_attr_values()
        self.materials_to_bill = self.technical_job_template_id.materials_to_bill if self.technical_job_template_id else False
        self.hs_bill = self.technical_job_template_id.bill_work_time if self.technical_job_template_id else False


    line_ids = fields.One2many('technical.job.note.assistant.line', 'wiz_id')

    technical_job_template_id = fields.Many2one('technical.job.sale.template', string="Plantilla venta")

    @api.onchange('select_tag_id')
    def onchange_select_tag_id(self):
        self.ensure_one()
        if self.select_tag_id:
            self.technical_job_template_tag_ids = [(4, self.select_tag_id.id)]
            self.select_tag_id = False

    select_tag_id = fields.Many2one('technical.job.sale.template.tag')
    technical_job_template_tag_ids = fields.Many2many('technical.job.sale.template.tag', 'technical_job_assistant_template_tag_rel', 'assistant_id', 'tag_id')

    @api.onchange('clean_selected_tags')
    def onchange_clean_selected_tags(self):
        if not self.clean_selected_tags:
            self.technical_job_template_tag_ids = [(5,)]
            self.clean_selected_tags = True

    clean_selected_tags = fields.Boolean(default=True)

    @api.depends('technical_job_template_tag_ids')
    def get_selected_tags_name(self):
        self.selected_tags_name = ' | '.join(self.technical_job_template_tag_ids.mapped('name'))
    selected_tags_name = fields.Char(compute=get_selected_tags_name)

    @api.depends('technical_job_template_tag_ids')
    def compute_template_tag_domain(self):
        for record in self:
            res = []
            if record.technical_job_id and record.technical_job_id.job_categ_ids.ids:
                res = [('categ_id','in',record.technical_job_id.job_categ_ids.ids)]
            if not record.technical_job_template_tag_ids:
               res.append(('first_selection', '=', True))
            else:
                res.append(('parent_tag_id.name', '=', record.technical_job_template_tag_ids[-1].name))
            record.template_tag_domain = json.dumps(res)
    template_tag_domain = fields.Char(compute=compute_template_tag_domain)

    @api.depends('technical_job_id', 'technical_job_template_tag_ids')
    def compute_template_domain(self):
        for record in self:
            res = []
            res.append(('tag_ids.categ_id.name','in',record.technical_job_id.job_categ_ids.mapped('name')))
            if record.technical_job_template_tag_ids:
                for tag in record.technical_job_template_tag_ids.mapped('name'):
                    res.append(('tag_ids.name', '=', tag))
            record.technical_job_template_domain = json.dumps(res)

    technical_job_template_domain = fields.Char(compute=compute_template_domain)

    new_opportunities = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Potencial otros trabajos")
    opportunities_description = fields.Text(string="Descripción oportunidad")
    opportunities_job_categ_id = fields.Many2one('technical.job.categ', string="Tipo oportunidad")
    currency_id = fields.Many2one('res.currency')
    content_type = fields.Char()
    pending_jobs = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Trabajos pendientes")
    needs_billing = fields.Selection(selection=[('yes', 'SI'), ('no', 'NO')], default="no", string="Necesita facturacion adicional?")
    add_generic_material = fields.Boolean(string="Otros materiales")
    generic_material_description = fields.Text(string="Adicionales")
    materials_to_bill = fields.Boolean(string="Materiales a facturar")
    generic_material_cost = fields.Float(string="Gasto materiales")
    materials_purchased = fields.Boolean(string="¿Se compraron materiales?")

    @api.depends('generic_material_cost', 'line_ids', 'add_generic_material', 'generic_material_cost', 'material_displacement', 'material_displacement_product_ids')
    def compute_material_price(self):
        for record in self:
            res = 0
            if record.materials_to_bill:
                company = self.env.user.company_id
                #template product price
                if record.technical_job_template_id and record.line_ids:
                    res += sum(record.line_ids.mapped('product_price'))
                #aditional material price
                if record.add_generic_material and record.generic_material_cost:
                    res += record.generic_material_cost*(company.material_rentability_multiplier or 1)
                #material displacement price
                if record.material_displacement and record.material_displacement_product_ids:
                    res += sum(record.material_displacement_product_ids.mapped('lst_price'))
            record.material_final_price = res
    material_final_price = fields.Float(string="Precio final materiales", compute=compute_material_price)

    material_displacement = fields.Boolean(string="Extra desplazamiento material")
    material_displacement_product_ids = fields.Many2many('product.product', 'material_displacement_product_assistant_rel', 'wiz_id', 'product_id')



    @api.depends('technical_job_id', 'technical_job_template_id')
    def compute_time_to_bill(self):
        for record in self:
            res = 0
            if record.technical_job_id and record.technical_job_id.time_register_ids:
                res = sum(record.technical_job_id.time_register_ids.filtered(lambda x: not x.displacement).mapped('total_min'))/60
            company = self.env.user.company_id
            billing_unit = company.min_billing_time_hs
            billing_relation_unit = res/billing_unit if billing_unit else 0

            if billing_relation_unit - int(billing_relation_unit) == 0:
                rounded_time = res
            else:
                rounded_time = int(billing_relation_unit)*billing_unit + billing_unit
            if self.technical_job_template_id and self.technical_job_template_id.limit_work_time:
                if rounded_time < self.technical_job_template_id.min_hs_to_bill:
                    rounded_time = self.technical_job_template_id.min_hs_to_bill
                elif rounded_time > self.technical_job_template_id.max_hs_to_bill:
                    rounded_time = self.technical_job_template_id.max_hs_to_bill
            record.rounded_time_to_bill = rounded_time
            record.hs_to_bill = res

    hs_bill = fields.Boolean(string="Facturar tiempo en domicilio")
    hs_to_bill = fields.Float(string="Tiempo registrado", compute=compute_time_to_bill)
    rounded_time_to_bill = fields.Float(string="Tiempo a facturar", compute=compute_time_to_bill)
    time_exception = fields.Boolean(string="Seleccion manual hs")
    manual_hs = fields.Float(string="Tiempo manual")
    job_employee_ids = fields.Many2many(related='technical_job_id.job_employee_ids', readonly=False)

    @api.depends('job_employee_ids', 'hs_bill', 'rounded_time_to_bill', 'manual_hs', 'time_exception')
    def compute_amount_hs_to_bill(self):
        self.ensure_one()
        res = 0
        hs_to_bill = self.rounded_time_to_bill
        if self.time_exception:
            hs_to_bill = self.manual_hs
        if self.hs_bill and self.job_employee_ids and self.hs_to_bill:
            for employee in self.job_employee_ids:
                res += hs_to_bill*employee.timesheet_cost
        self.amount_hs_to_bill = res
    amount_hs_to_bill = fields.Float(compute=compute_amount_hs_to_bill, string="Total M.O.")

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
    todo_description = fields.Text(string="A realizar")

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
        if self.content_type == 'Finalizacion trabajo' and self.needs_billing=='yes' and self.materials_to_bill:
            if self.line_ids.filtered(lambda x: not x.product_id):
                raise UserError('Materiales: Falta personalización de algunos productos')
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
                    for line in self.prepare_billing_time_lines():
                        lines.append((0, 0, line))
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

    def prepare_billing_time_lines(self):
        no_cost_employees = self.job_employee_ids.filtered(lambda x: not x.timesheet_cost)
        if no_cost_employees:
            raise ValidationError(f"Error: Empleados sin costo de mano de obra: {','.join(no_cost_employees.mapped('name'))}")

        hs_to_bill = self.rounded_time_to_bill
        if self.time_exception:
            hs_to_bill = self.manual_hs

        company = self.env.user.company_id
        lines_dict = {}
        for employee in self.job_employee_ids:
            k = employee.technical_time_sale_line_product_id if employee.technical_time_sale_line_product_id else company.billing_time_product_id
            if not k:
                raise ValidationError(
                    f"Error: Empleados sin producto de mano de obra. Contactese con el administrador del sistema para realizar las configuraciones correspondientes.")

            if k not in lines_dict.keys():
                lines_dict[k] = f'1|{employee.timesheet_cost*hs_to_bill}'
            else:
                existing_value = lines_dict[k]
                qty = int(existing_value.split('|')[0]) + 1
                amount = float(existing_value.split('|')[1]) + employee.timesheet_cost*hs_to_bill
                lines_dict[k] = f'{qty}|{amount}'
        vals = []
        for key, value in lines_dict.items():
            qty = int(value.split('|')[0])
            amount = float(value.split('|')[1])
            vals.append({
                'product_id': key.id,
                'name': f'{key.name} (x{qty} - {hs_to_bill} hs) | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
                'product_uom_qty': 1,
                'price_unit': amount,
            })
        return vals


