from odoo import fields, models, api
import json

class ProductTemplate(models.Model):
    _inherit = "product.template"

    variant_combo_config_ids = fields.One2many('product.variant.combo.config', 'product_template_id', copy=True)
    is_variant_combo = fields.Boolean(string="Es Combo?")


class ProductVariantComboConfig(models.Model):
    _name = "product.variant.combo.config"

    product_template_id = fields.Many2one('product.template', string="Plantilla producto")
    product_uom_qty = fields.Float(string="Cantidad", default=1)
    available_product_tmpl_domain = fields.Char(string="Filtro Plantillas")
    line_ids = fields.Many2many('product.variant.combo.config.line', 'variant_combo_config_table_rel','config_id', 'line_id', string="Reglas asignacion")

class ProductVariantComboConfigLine(models.Model):
    _name = "product.variant.combo.config.line"



    attribute_value_id = fields.Many2one('product.attribute.value', string="Valor de atributo")
    domain_term = fields.Char(string="Filtro productos")
    name = fields.Char(string="Nombre")

class ProductVariantComboLine(models.Model):
    _name = "product.variant.combo.line"

    parent_product_id = fields.Many2one('product.product', string="Producto Padre")
    product_id = fields.Many2one('product.product', string="Producto")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', string="Plantilla Producto")
    product_domain = fields.Char()
    product_uom_qty = fields.Float(string="Cantidad")

    standard_price = fields.Float(related='product_id.standard_price', string="Costo")
    lst_price = fields.Float(related='product_id.lst_price', string="Precio Venta")
    currency_id = fields.Many2one('res.currency', readonly=1)


class ProductProduct(models.Model):
    _inherit = "product.product"


    @api.depends('combo_variant_line_ids', 'combo_variant_line_ids.product_id', 'combo_variant_line_ids.product_uom_qty', 'product_tmpl_id.is_variant_combo' )
    def sync_combo_bom_values(self):
        for record in self:
            combo_mrp_bom_list = False
            if record.product_tmpl_id.is_variant_combo and record.combo_variant_line_ids:
                combo_mrp_bom_list = record.combo_mrp_bom_list_id
                if not combo_mrp_bom_list:
                    combo_mrp_bom_list = self.env['mrp.bom'].create({'product_tmpl_id': record.product_tmpl_id.id, 'product_id': record.id})
                line_vals = [(5,)]
                for combo_component in record.combo_variant_line_ids:
                    line_vals.append((0, 0, {
                        'product_id': combo_component.product_id.id,
                        'product_qty': combo_component.product_uom_qty,
                    }))
                combo_mrp_bom_list.bom_line_ids = line_vals
            else:
                if record.combo_mrp_bom_list_id:
                    record.combo_mrp_bom_list_id.sudo().unlink()
            record.combo_mrp_bom_list_id = combo_mrp_bom_list.id if combo_mrp_bom_list else False

    combo_mrp_bom_list_id = fields.Many2one('mrp.bom', compute=sync_combo_bom_values, store=True)
    no_update_combo_lines = fields.Boolean(string="Configuracion manual")
    combo_variant_line_ids = fields.One2many('product.variant.combo.line', 'parent_product_id', string="Componentes Combo")

    @api.depends('name', 'product_template_variant_value_ids')
    def compute_complete_name(self):
        for record in self:
            name = record.name + ")"
            name += ','.join(record.product_template_variant_value_ids.mapped('product_attribute_value_id.display_name'))
            name += ")"
            record.complete_name = name


    complete_name = fields.Char(compute=compute_complete_name, store=True, string="Nombre Completo (busqueda)")

    @api.depends('product_tmpl_id.variant_combo_config_ids', 'product_tmpl_id.is_variant_combo', 'product_tmpl_id.variant_combo_config_ids.product_template_id', 'product_tmpl_id.variant_combo_config_ids.available_product_tmpl_domain', 'product_tmpl_id.variant_combo_config_ids.line_ids')
    def combo_product_assigment(self):
        template_obj = self.env['product.template']
        product_obj = self.env['product.product']
        for record in self:
            if record.product_tmpl_id.variant_combo_config_ids and not record.no_update_combo_lines:
                combo_variant_line_vals = [(5,)]
                product_attr_names = record.product_template_variant_value_ids.mapped('product_attribute_value_id.display_name')
                for combo_config in record.product_tmpl_id.variant_combo_config_ids:
                    vals = {
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'product_uom_qty': combo_config.product_uom_qty
                            }
                    available_templates = template_obj.search(json.loads(combo_config.available_product_tmpl_domain.replace('True', 'true').replace('False', 'false'))).mapped('id')
                    domain = [('product_tmpl_id.id', 'in', available_templates)]
                    for combo_config_line in combo_config.line_ids:
                        if combo_config_line.attribute_value_id.display_name in product_attr_names:
                            domain.extend(eval(combo_config_line.domain_term.replace("'", '"').replace('True', 'true').replace('False', 'false')))
                    matching_products = product_obj.search(domain)
                    if not matching_products:
                        vals['product_id'] = available_templates[0].product_variant_ids[0].id
                        vals['product_domain'] = json.dumps([('product_tmpl_id.id', 'in', available_templates)])
                    else:
                        vals['product_domain'] = json.dumps(domain)
                        vals['product_id'] = matching_products[0].id
                    combo_variant_line_vals.append((0, 0, vals))
                record.combo_variant_line_ids = combo_variant_line_vals
            record.trigger_combo_product_assigment = False if record.trigger_combo_product_assigment else True

    trigger_combo_product_assigment = fields.Boolean(compute=combo_product_assigment, store=True)