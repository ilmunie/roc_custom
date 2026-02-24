import json
import logging
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class SaleCommercialMaterialRule(models.Model):
    _name = 'sale.commercial.material.rule'
    _description = 'Regla de Material Comercial'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    domain = fields.Char(default='[]')
    attachment_ids = fields.Many2many('ir.attachment', string="Archivos adjuntos")
    active = fields.Boolean(default=True)


class SaleOrderCommercialMaterial(models.Model):
    _inherit = 'sale.order'

    commercial_material_ids = fields.Many2many(
        'ir.attachment',
        string="Material Comercial",
        compute='_compute_commercial_material_ids',
        store=False,
    )

    def _compute_commercial_material_ids(self):
        for order in self:
            attachment_ids = []
            self.env.cr.execute(
                "SELECT id, domain FROM sale_commercial_material_rule WHERE active = true ORDER BY sequence, id"
            )
            rules = self.env.cr.fetchall()
            for rule_id, domain_str in rules:
                try:
                    domain = json.loads(domain_str or '[]')
                except (json.JSONDecodeError, TypeError):
                    continue
                domain.append(('id', '=', order.id))
                if self.env['sale.order'].search_count(domain):
                    self.env.cr.execute(
                        "SELECT ir_attachment_id FROM ir_attachment_sale_commercial_material_rule_rel "
                        "WHERE sale_commercial_material_rule_id = %s",
                        (rule_id,)
                    )
                    attachment_ids.extend(r[0] for r in self.env.cr.fetchall())
            order.commercial_material_ids = list(set(attachment_ids))
