
from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = "product.product"

    def replace_product(self):
        product_to_replace = self.env['product.product'].browse(self._context.get('active_ids', []))
        wiz_line_vals = []
        for product in product_to_replace:
            template = product.product_tmpl_id
            template_attr_ids = template.mapped('attribute_line_ids.attribute_id.id')
            if all(template_attr_id in product.mapped('product_template_variant_value_ids.attribute_id.id') for template_attr_id in template_attr_ids):
                attributes_values_to_match = product.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in template_attr_ids)
                new_product = template.product_variant_ids.filtered(lambda x: all(attr_to_match.id in x.product_template_variant_value_ids.mapped('id') for attr_to_match in attributes_values_to_match))
                if new_product:
                    wiz_line_vals.append((0, 0, {'old_product_id': product.id, 'new_product_id': new_product.id}))
                else:
                    wiz_line_vals.append((0, 0, {'old_product_id': product.id}))
            else:
                wiz_line_vals.append((0,0, {'old_product_id': product.id}))
        wiz_id = self.env['product.replacement.wiz'].create({'line_ids': wiz_line_vals})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.replacement.wiz',
            'res_id': wiz_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class ProductReplacementWiz(models.Model):
    _name = "product.replacement.wiz"

    line_ids = fields.One2many('product.replacement.wiz.line', 'wiz_id')

    def action_done(self):
        fields_to_update = self.env['ir.model.fields'].search([('store', '=', True),('model', 'not ilike', 'stock_warn_insufficient_qty'),('model', 'not ilike', 'report'), ('relation', '=', 'product.product'), ('ttype', '=', 'many2one'), ('model_id.transient', '=', False)])
        for line in self.line_ids.filtered(lambda x: x.old_product_id and x.new_product_id):
            for field_to_update in fields_to_update:
                    query = f"""
                            UPDATE {field_to_update.model.replace('.', '_')} 
                            SET {field_to_update.name} = %s
                            WHERE {field_to_update.name} = %s
                        """
                    self.env.cr.execute(query, (line.new_product_id.id, line.old_product_id.id))
        self.env.cr.commit()
        return False

class ProductReplacementWizLine(models.Model):
    _name = "product.replacement.wiz.line"

    wiz_id = fields.Many2one('product.replacement.wiz')

    old_product_id = fields.Many2one('product.product')
    new_product_id = fields.Many2one('product.product')