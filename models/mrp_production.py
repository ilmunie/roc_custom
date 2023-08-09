from odoo import fields, models, api

class MrpProduction(models.Model):
    _inherit = 'mrp.production'


    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            name += " | " + dict(rec._fields['state']._description_selection(self.env)).get(rec.state)
            if rec.components_availability:
                name += " | " + rec.components_availability
            res.append((rec.id, name))
        return res
    purchase_order_ids = fields.Many2many(comodel_name='purchase.order', compute='_compute_purchase_order_link', store=True)

    @api.depends('procurement_group_id.stock_move_ids.created_purchase_line_id.order_id', 'procurement_group_id.stock_move_ids.move_orig_ids.purchase_line_id.order_id')
    def _compute_purchase_order_link(self):
        for production in self:
            po_ids = []
            stock_moves_pg = production.procurement_group_id.stock_move_ids
            for move in stock_moves_pg:
                if move.created_purchase_line_id:
                    po_ids.append(move.created_purchase_line_id.order_id.id)
                if move.move_orig_ids:
                    for move_org in move.move_orig_ids:
                        if move_org.purchase_line_id:
                            po_ids.append(move_org.purchase_line_id.order_id.id)
            production.purchase_order_ids = [(6,0,po_ids)]

    sale_order_ids = fields.Many2many(comodel_name='sale.order',compute='_compute_sale_order_link', store=True)

    @api.depends('procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id')
    def _compute_sale_order_link(self):
        for production in self:
            so_ids = []
            if production.procurement_group_id and production.procurement_group_id.mrp_production_ids:
                for mrp_prod in production.procurement_group_id.mrp_production_ids:
                    for move in mrp_prod.move_dest_ids:
                        if move.group_id and move.group_id.sale_id:
                            so_ids.append(move.group_id.sale_id.id)
            production.sale_order_ids = [(6,0,so_ids)]
