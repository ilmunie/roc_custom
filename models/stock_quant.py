from odoo import fields, models, api
import json

class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.depends('product_id')
    def get_pta(self):
        for record in self:
            res = []
            if record.product_id:
                res.append((6,0,record.product_id.product_template_attribute_value_ids.mapped('id')))
            record.product_template_attribute_value_ids = res
    product_template_attribute_value_ids = fields.Many2many('product.template.attribute.value', compute=get_pta, store=True)

    product_categ_id = fields.Many2one(related='product_id.categ_id', store=True)
