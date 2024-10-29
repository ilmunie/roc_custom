import pdb

from odoo import fields, models, api
import json
from odoo.exceptions import UserError, ValidationError

class TechnicalJobBillingAssistantLine(models.TransientModel):
    _name = "technical.job.billing.assistant.line"



    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id and self.product_id.product_template_variant_value_ids:
            if self.product_id.product_template_variant_value_ids.mapped('product_attribute_value_id.id') != self.attr_value_ids.mapped('id'):
                self.attr_value_ids = [(6, 0, self.product_id.product_template_variant_value_ids.mapped('product_attribute_value_id.id'))]
        return False


    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", readonly=False, force_save=True)

    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', default=True)
    @api.depends('product_id')
    def _compute_product_updatable(self):
        for line in self:
                line.product_updatable = True
    product_custom_attribute_value_ids = fields.One2many('product.attribute.custom.value', 'wiz_line_creator_id', string="Custom Values WIZ", copy=True)
    product_no_variant_attribute_value_ids = fields.Many2many('product.template.attribute.value', 'variant_creator_wiz_rel', 'wiz_id', 'attr_tmp_value_id', string="Extra Values", ondelete='restrict')
    is_configurable_product = fields.Boolean('Is the product configurable?', related="product_template_id.has_configurable_attributes")
    product_template_attribute_value_ids = fields.Many2many(related='product_id.product_template_attribute_value_ids', readonly=True)
    product_tmpl_domain = fields.Char()
    wiz_id = fields.Many2one('technical.job.billing.assistant')
    #product_template_id = fields.Many2one('product.template', string="Producto")
    attr_readonly = fields.Boolean()
    product_price = fields.Float(string="Precio unitario", related='product_id.lst_price')
    @api.depends('product_price', 'product_uom_qty')
    def compute_total_price(self):
        for record in self:
            record.total_price = record.product_price*record.product_uom_qty

    total_price = fields.Float(string="Precio total",compute=compute_total_price)
    product_uom_qty = fields.Float(string="Cantidad")
    currency_id = fields.Many2one(related='wiz_id.currency_id')
    discount = fields.Float()

    attr_value_ids = fields.Many2many('product.attribute.value', 'billing_assist_attr_value_rel', 'wiz_id', 'attr_value_id', string="Personalizaciones")

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
    line_id = fields.Many2one('technical.job.sale.template.line')

class TechnicalJobBillingAssistant(models.TransientModel):
    _name = "technical.job.billing.assistant"

    technical_job_id = fields.Many2one('technical.job')

    @api.onchange('general_discount')
    def onchange_general_discount(self):
        if self.general_discount>0:
            self.materials_discount = self.general_discount
            self.generic_materials_discount = self.general_discount
            self.mo_discount = self.general_discount
            self.displacement_discount = self.general_discount
            for line in self.line_ids:
                line.discount = self.general_discount

    @api.onchange('materials_discount')
    def onchange_materials_discount(self):
        if self.materials_discount>0 and self.materials_discount!= self.general_discount:
            for line in self.line_ids:
                line.discount = self.materials_discount
            self.generic_materials_discount = self.materials_discount

    general_discount = fields.Float(string="Dcto Gral")
    materials_discount = fields.Float(string="Dcto Materiales")
    generic_materials_discount = fields.Float(string="Dcto Material")
    mo_discount = fields.Float(string="Dcto MO")
    displacement_discount = fields.Float(string="Dcto Desplazamiento")

    @api.onchange('technical_job_template_id', 'technical_job_template_tag_ids')
    def onchange_technical_job_template_id(self):
        self.ensure_one()
        vals = [(5,)]
        mo_discount = 0
        if self.general_discount:
            mo_discount = self.general_discount
        elif self.mo_discount:
            mo_discount = self.mo_discount
        for line in self.technical_job_template_id.line_ids:
            product_tmpl = line.product_tmpl_id
            if product_tmpl:
                tmpl_domain = [('id', '=', line.product_tmpl_id.id)]
            else:
                tmpl_domain = json.loads(line.product_tmpl_domain.replace('True', 'true').replace('False', 'false'))
                name_tags = self.technical_job_template_tag_ids.filtered(
                    lambda x: x.appears_in_template_name)
                if line.product_name_tag_ids:
                    name_tags = name_tags.filtered(lambda x: x.name in line.product_name_tag_ids.mapped('name'))
                for name_tag in name_tags:
                    tmpl_domain.insert(0, json.loads(name_tag.search_domain_term.replace('True', 'true').replace('False', 'false'))[0])
                available_tmpls = self.env['product.template'].search(tmpl_domain)
                product_tmpl = available_tmpls[0] if available_tmpls else False
            available_products = product_tmpl.product_variant_ids
            select_product = False
            attr_val = False
            for product in available_products:
                matching_attr_values = line.default_attr_value_ids.filtered(lambda r: r.attribute_id.display_name in product.product_template_attribute_value_ids.mapped('attribute_id.display_name'))
                if all( mat_attr_name in product.product_template_variant_value_ids.mapped('product_attribute_value_id.display_name') for mat_attr_name in matching_attr_values.mapped('display_name')):
                    select_product = product
                    break
            if not select_product:
                select_product = product_tmpl.product_variant_ids[0]
            vals.append((0, 0,
                         {'product_template_id': product_tmpl.id,
                          'line_id': line.id,
                          'attr_readonly': True,
                          'product_tmpl_domain': json.dumps(tmpl_domain),
                          'product_uom_qty': line.product_uom_qty,
                          'discount': line.default_discount if not mo_discount else self.general_discount,
                          'product_id': select_product.id}))

        self.line_ids = vals
        for line in self.line_ids:
            line.onchange_product_id()
        self.materials_to_bill = self.technical_job_template_id.materials_to_bill if self.technical_job_template_id else False
        self.general_discount = self.technical_job_template_id.default_general_discount if self.technical_job_template_id else 0
        self.materials_discount = self.technical_job_template_id.default_materials_discount if self.technical_job_template_id else 0
        self.mo_discount = self.technical_job_template_id.default_mo_discount if self.technical_job_template_id else 0
        self.displacement_discount = self.technical_job_template_id.default_displacement_discount if self.technical_job_template_id else 0
        self.hs_bill = self.technical_job_template_id.bill_work_time if self.technical_job_template_id else False


    line_ids = fields.One2many('technical.job.billing.assistant.line', 'wiz_id')

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

    add_generic_material = fields.Boolean(string="Otros materiales")
    generic_material_description = fields.Text(string="Adicionales")
    materials_to_bill = fields.Boolean(string="Materiales a facturar")
    generic_material_cost = fields.Float(string="Gasto materiales")
    materials_purchased = fields.Boolean(string="¿Se compraron materiales?")

    @api.model
    def name_get(self):
        res = []
        for rec in self:
            name = 'FACTURACIÓN OPERACIONES'
            res.append((rec.id, name))
        return res


    @api.depends('generic_material_cost','displacement_discount','generic_materials_discount','line_ids.discount', 'line_ids', 'add_generic_material', 'generic_material_cost', 'material_displacement', 'material_displacement_product_ids')
    def compute_material_price(self):
        for record in self:
            res = 0
            if record.materials_to_bill:
                company = self.env.user.company_id
                #template product price
                if record.technical_job_template_id and record.line_ids:
                    for line in record.line_ids:
                        res += line.total_price*(1 - line.discount)
                #aditional material price
                if record.add_generic_material and record.generic_material_cost:
                    res += record.generic_material_cost*(company.material_rentability_multiplier or 1)*(1 - record.generic_materials_discount)
                #material displacement price
                if record.material_displacement and record.material_displacement_product_ids:
                    res += (sum(record.material_displacement_product_ids.mapped('lst_price'))*(1 - record.displacement_discount))
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

    @api.depends('job_employee_ids', 'mo_discount', 'hs_bill', 'rounded_time_to_bill', 'manual_hs', 'time_exception')
    def compute_amount_hs_to_bill(self):
        self.ensure_one()
        res = 0
        hs_to_bill = self.rounded_time_to_bill
        if self.time_exception:
            hs_to_bill = self.manual_hs
        if self.hs_bill and self.job_employee_ids and hs_to_bill:
            for employee in self.job_employee_ids:
                res += hs_to_bill*employee.timesheet_cost
        self.amount_hs_to_bill = res*(1 - self.mo_discount)
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


    @api.model
    def default_get(self, fields):
        result = super(TechnicalJobBillingAssistant, self).default_get(fields)
        result['technical_job_id'] = self.env.context.get("technical_job", False)
        result['currency_id'] = self.env.user.company_id.currency_id.id
        return result

    currency_id = fields.Many2one('res.currency')


    def action_done(self):
        if self.materials_to_bill:
            if self.line_ids.filtered(lambda x: not x.product_id):
                raise UserError('Materiales: Falta personalización de algunos productos')
        if len(self.displacement_product_ids.mapped('id')) > 1:
            raise UserError('Solo puede seleccionar un tipo de desplazamiento')
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
            for line in self.prepare_template_notes():
                lines.append((0, 0, line))
            if self.materials_to_bill:
                for line in self.prepare_material_cost_lines():
                    lines.append((0, 0, line))
            if self.displacement_product_ids:
                for line in self.prepare_displacement_lines():
                    lines.append((0, 0, line))
            if self.rounded_time_to_bill and self.hs_bill:
                for line in self.prepare_billing_time_lines():
                    lines.append((0, 0, line))

            #link to tickets - opportunity_id
            ticket_id = real_rec.id if real_rec._name == 'helpdesk.ticket' else False
            opportunity_id = False
            if real_rec._name == 'crm.lead':
                opportunity_id = real_rec.id
            if not opportunity_id and real_rec._name == 'helpdesk.ticket':
                if real_rec.res_model == 'crm.lead':
                    opportunity_id = real_rec.res_id
                elif real_rec.res_model == 'sale.order' and real_rec.src_rec and real_rec.src_rec.opportunity_id:
                    opportunity_id = real_rec.src_rec.opportunity_id.id
            if lines:
                so_vals = {
                    'order_line': lines,
                    'date_order': fields.Date.context_today(self),
                    #'warehouse': '',
                    'partner_id': real_rec.partner_id.id if real_rec else False,
                    'partner_invoice_id': real_rec.partner_id.id if real_rec else False,
                    'partner_shipping_id': real_rec.partner_id.id if real_rec else False,
                    'journal_id': company.default_job_billing_journal_id.id if company.default_job_billing_journal_id else False,
                    'opportunity_id': opportunity_id,
                    'ticket_id': ticket_id ,
                    'user_id': real_rec.user_id.id if real_rec and real_rec.user_id else self.env.user.id,
                    'team_id': real_rec.team_id.id if real_rec and 'team_id' in real_rec._fields.keys() and real_rec.team_id else False,
                    'require_signature': True,
                    'origin': self.technical_job_id.display_name,
                }
                existing_po = self.env['sale.order'].create(so_vals)
        else:
            lines = []
            for line in self.prepare_template_notes():
                lines.append((0, 0, line))
            if self.materials_to_bill:
                for line in self.prepare_material_cost_lines():
                    lines.append((0, 0, line))
            if self.displacement_product_ids:
                for line in self.prepare_displacement_lines():
                    lines.append((0, 0, line))
            if self.rounded_time_to_bill and self.hs_bill:
                for line in self.prepare_billing_time_lines():
                    lines.append((0, 0, line))
            if lines:
                so_write_vals = {
                    'order_line': lines,
                    'origin': existing_po.origin + " " + self.technical_job_id.display_name
                }
                existing_po.write(so_write_vals)
        if self.technical_job_id and self.technical_job_id.schedule_id:
            self.technical_job_id.schedule_id.sale_order_ids = [(4, existing_po.id)]
        return {
            "type": "ir.actions.act_window",
            "res_model": "technical.job",
            "views": [[False, "form"]],
            "res_id": self.technical_job_id.id
        }

    def prepare_material_cost_lines(self):
        company = self.env.user.company_id
        vals = []
        #section
        vals.append({
            'display_type': 'line_section',
            'name': 'MATERIALES',
        })
        #template materials
        if self.technical_job_template_id and self.line_ids:
            for line in self.line_ids:
                vals.append({
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'price_unit':  line.product_price,
                    'discount':  line.discount*100,
                    'name': f'{line.product_id.name} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
                })
        #generic material
        if self.add_generic_material:
            vals.append({
                'product_id': company.material_product_id.id,
                'product_uom_qty': 1,
                'discount': self.generic_materials_discount*100,
                'price_unit': self.generic_material_cost*company.material_rentability_multiplier,
                'name': f'{self.generic_material_description or company.material_product_id.name} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
            })
        #material displacement
        if self.material_displacement:
            for line in self.material_displacement_product_ids:
                vals.append({
                    'product_id': line.id,
                    'discount': self.materials_discount*100,
                    'name': f'Adquisición materiales: {line.name} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
                    'product_uom_qty': 1,
                })
        return vals

    def prepare_template_notes(self):
        vals = []
        for note in self.technical_job_template_id.note_ids:
            vals.append({
                'display_type': 'line_note',
                'name': note.name
            })
        return vals

    def prepare_displacement_lines(self):
        vals = []
        vals.append({
            'display_type': 'line_section',
            'name': 'DESPLAZAMIENTO',
        })
        vals.append({
            'product_id': self.displacement_product_ids.mapped('id')[0],
            'name': f'{self.displacement_product_ids.mapped("name")[0]} | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
            'product_uom_qty': 1,
            'discount': self.displacement_discount*100,
        })
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
        vals.append({
            'display_type': 'line_section',
            'name': 'MANO DE OBRA',
        })
        for key, value in lines_dict.items():
            qty = int(value.split('|')[0])
            amount = float(value.split('|')[1])
            vals.append({
                'product_id': key.id,
                'name': f'{key.name} (x{qty} - {hs_to_bill} hs) | Visita {fields.Datetime.now().strftime("%d-%m-%Y")}',
                'product_uom_qty': 1,
                'price_unit': amount,
                'discount': self.mo_discount*100,
            })
        return vals