from odoo import fields, models, api
import json

class TechnicalJobSaleTemplateNote(models.Model):
    _name = "technical.job.sale.template.note"
    _order = 'sequence,name'


    name = fields.Char('Nombre', required=True)
    template_id = fields.Many2one('technical.job.sale.template')
    sequence = fields.Integer()


class TechnicalJobSaleTemplateTag(models.Model):
    _name = "technical.job.sale.template.tag"

    name = fields.Char('Nombre', required=True)
    first_selection = fields.Boolean(string="Primer seleccion")
    categ_id = fields.Many2one('technical.job.categ', string="Categoria Trabajo Tecnico")
    parent_tag_id = fields.Many2many('technical.job.sale.template.tag', 'tag_parent_rel_table','parent_tag','child_tag', string="Etiqueta Padre")
    sequence = fields.Integer()
    appears_in_template_name = fields.Boolean(string="Aparece nombre Producto")
    search_text = fields.Char()
    search_type = fields.Selection([('ilike', 'Contiene'), ('not ilike', 'No contiene')], default="ilike")

    @api.onchange('name')
    def onchange_name(self):
        for record in self:
            if record.search_text != record.name:
                record.search_text = record.name

    @api.depends('search_text', 'search_type')
    def compute_search_domain_term(self):
        for record in self:
            record.search_domain_term = json.dumps([('name',record.search_type, record.search_text)])

    search_domain_term = fields.Char(compute=compute_search_domain_term, store=True)



class TechnicalJobSaleTemplate(models.Model):
    _name = "technical.job.sale.template"

    note_ids = fields.One2many('technical.job.sale.template.note', 'template_id')
    name = fields.Char('Nombre', required=True)
    tag_ids = fields.Many2many('technical.job.sale.template.tag', 'job_sale_template_tag_rel', 'template_id', 'tag_id', string='Categorias')
    materials_to_bill = fields.Boolean(string="Materiales a facturar")
    bill_work_time = fields.Boolean(string="Facturar hs en domicilio")
    limit_work_time = fields.Boolean(string="Limite facturación tiempo")
    min_hs_to_bill = fields.Float(string="Hs min")
    max_hs_to_bill = fields.Float(string="Hs max")
    line_ids = fields.One2many('technical.job.sale.template.line', 'template_id')
    default_general_discount = fields.Float(string="Descuento General")
    default_materials_discount = fields.Float(string="Descuento en materiales")
    default_mo_discount = fields.Float(string="Descuento MO")
    default_displacement_discount = fields.Float(string="Descuento en desplazamiento")

class TechnicalJobSaleTemplateLine(models.Model):
    _name = "technical.job.sale.template.line"
    _order = 'sequence'

    template_id = fields.Many2one('technical.job.sale.template')

    @api.depends('template_id.tag_ids')
    def get_product_name_tag_domain(self):
        for record in self:
            res = []
            tags = record.template_id.tag_ids.filtered(lambda x: x.appears_in_template_name)
            if tags:
                res = [('name', 'in', tags.mapped('name'))]

            record.product_name_tag_domain = json.dumps(res)

    product_name_tag_domain = fields.Char(compute=get_product_name_tag_domain)
    product_name_tag_ids = fields.Many2many('technical.job.sale.template.tag', 'job_sale_line_template_tag_rel', 'line_id', 'tag_id',)
    product_tmpl_domain = fields.Char()
    product_tmpl_id = fields.Many2one('product.template', string="Plantilla Producto")
    product_uom_qty = fields.Float(string="Cant")
    sequence = fields.Integer()

    @api.depends('product_tmpl_domain','product_tmpl_id', 'default_attr_value_ids')
    def compute_attr_value_domain(self):
        for record in self:
            res = []
            if record.product_tmpl_id:
                res = [('id', 'in', record.product_tmpl_id.mapped('product_variant_ids').mapped('product_template_variant_value_ids.product_attribute_value_id.id'))]
            elif record.product_tmpl_domain:
                for prod_tmp in self.env['product.template'].search(json.loads(record.product_tmpl_domain.replace('True', 'true').replace('False', 'false'))):
                    if len(res) > 0:
                        res.insert(0, '|')
                    res.append(('id', 'in', prod_tmp.mapped('product_variant_ids').mapped('product_template_variant_value_ids.product_attribute_value_id.id')))
            if record.default_attr_value_ids:
                res.append(('attribute_id.id', 'not in', record.default_attr_value_ids.mapped('attribute_id.id')))
            if not res:
                res = [('id', '=', 1)]
            record.attr_value_domain = json.dumps(res)

    attr_value_domain = fields.Char(compute=compute_attr_value_domain)
    default_attr_value_ids = fields.Many2many('product.attribute.value', string="Atributos por defecto")
    product_id = fields.Many2one('product.product')
    default_discount = fields.Float(string="Dcto por default")