from odoo import fields, models, api
import json

class TechnicalJobSaleTemplateTag(models.Model):
    _name = "technical.job.sale.template.tag"

    name = fields.Char('Nombre', required=True)
    first_selection = fields.Boolean(string="Primer seleccion")
    categ_id = fields.Many2one('technical.job.categ', string="Categoria Trabajo Tecnico")
    parent_tag_id = fields.Many2many('technical.job.sale.template.tag', 'tag_parent_rel_table','parent_tag','child_tag', string="Etiqueta Padre")
    sequence = fields.Integer()

class TechnicalJobSaleTemplate(models.Model):
    _name = "technical.job.sale.template"

    name = fields.Char('Nombre', required=True)
    tag_ids = fields.Many2many('technical.job.sale.template.tag', 'job_sale_template_tag_rel', 'template_id', 'tag_id', string='Categorias')

    materials_to_bill = fields.Boolean(string="Materiales a facturar")
    bill_work_time = fields.Boolean()
    limit_work_time = fields.Boolean(string="Limite facturación tiempo")
    min_hs_to_bill = fields.Float(string="Hs min")
    max_hs_to_bill = fields.Float(string="Hs max")
    line_ids = fields.One2many('technical.job.sale.template.line', 'template_id')

class TechnicalJobSaleTemplateLine(models.Model):
    _name = "technical.job.sale.template.line"

    template_id = fields.Many2one('technical.job.sale.template')
    product_tmpl_id = fields.Many2one('product.template')


    @api.depends('product_tmpl_id', 'default_attr_value_ids')
    def compute_attr_value_domain(self):
        for record in self:
            res = [('id', 'in', record.product_tmpl_id.mapped('product_variant_ids').mapped('product_template_variant_value_ids.product_attribute_value_id.id'))]
            if record.default_attr_value_ids:
                res.append(('attribute_id.id', 'not in', record.default_attr_value_ids.mapped('attribute_id.id')))
            if not res:
                res = [('id', '=', 1)]
            record.attr_value_domain = json.dumps(res)

    attr_value_domain = fields.Char(compute=compute_attr_value_domain)
    default_attr_value_ids = fields.Many2many('product.attribute.value', string="Atributos por defecto")
    product_id = fields.Many2one('product.product')