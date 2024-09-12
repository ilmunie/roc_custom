from odoo import fields, models, api



class ProductAttributeCustomValue(models.Model):
    _inherit = "product.attribute.custom.value"

    wiz_line_creator_id = fields.Many2one('technical.job.billing.variant.creator')





