from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"
    min_billing_time_hs = fields.Float(string="Tiempo minimo facturacion")
    billing_time_product_id = fields.Many2one('product.product', string="Producto tiempo en domicilio")
    displacement_product_ids = fields.Many2many('product.product', string="Productos desplazamiento")
    material_product_id = fields.Many2one('product.product', string="Producto materiales")
    material_rentability_multiplier = fields.Float(string="Rentabilidad costo materiales")
    default_job_billing_journal_id = fields.Many2one('account.journal', string="Diario facturacion")

class ResCompanySettings(models.TransientModel):
    _inherit = "res.config.settings"

    min_billing_time_hs = fields.Float(related='company_id.min_billing_time_hs', readonly=False)
    material_rentability_multiplier = fields.Float(related='company_id.material_rentability_multiplier', readonly=False)
    billing_time_product_id = fields.Many2one(related='company_id.billing_time_product_id', readonly=False)
    displacement_product_ids = fields.Many2many(related='company_id.displacement_product_ids', readonly=False)
    material_product_id = fields.Many2one(related='company_id.material_product_id', readonly=False)
    job_billing_journal_id = fields.Many2one(related='company_id.default_job_billing_journal_id', readonly=False)
