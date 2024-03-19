from odoo import fields, models, api

class MrpProduction(models.Model):
    _inherit = 'mrp.production'


    state = fields.Selection(selection_add=[('waiting_approval','Esperando Autorizacion')])
    already_confirmed = fields.Boolean()
    @api.depends('move_raw_ids', 'state', 'move_raw_ids.product_uom_qty')
    def _compute_unreserve_visible(self):
        for order in self:
            already_reserved = order.state not in ('done', 'cancel') and order.mapped('move_raw_ids.move_line_ids')
            any_quantity_done = any(m.quantity_done > 0 for m in order.move_raw_ids)

            order.unreserve_visible = not any_quantity_done and already_reserved
            order.reserve_visible = order.state in ('waiting_approval','confirmed', 'progress', 'to_close') and any(move.product_uom_qty and move.state in ['confirmed', 'partially_available'] for move in order.move_raw_ids)

    def button_confirm_with_approval(self):
        for record in self:
            confirm_group = self.env.ref('roc_custom.group_confirm_mrp', raise_if_not_found=False)
            if confirm_group:
                if self.env.user.id in confirm_group.users.mapped('id'):
                    return record.action_confirm()
            record.write({'state': 'waiting_approval'})

    def edit(self):
        for record in self:
            record.state = 'draft'
            record.already_confirmed = True

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
