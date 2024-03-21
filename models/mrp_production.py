from odoo import fields, models, api
import json


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.depends('bom_line_id')
    def get_alternative_prod_domain(self):
        for record in self:
            res = []
            if record.bom_line_id:
                if record.bom_line_id.match_attributes:
                    res.insert(0, ('product_tmpl_id', '=', record.bom_line_id.product_id.product_tmpl_id.id))
                    if record.bom_line_id.alternative_product_domain:
                        res.insert(0, '|')
                if record.bom_line_id.alternative_product_domain:
                    res.extend(json.loads(record.bom_line_id.alternative_product_domain))
            record.alternative_product_domain = json.dumps(res)

    alternative_product_domain = fields.Char(compute=get_alternative_prod_domain, store=True)

    def open_alternative_products(self):
        context = {
                'product_production_id': self.raw_material_production_id.product_id.id,
                'domain': self.alternative_product_domain,
                'move_id': self.id,
                'qty': self.product_uom_qty,
                'location': self.location_id.id,
                'attr_values': self.raw_material_production_id.product_id.product_template_variant_value_ids.mapped('id'),
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.alternative.product.assistant',
            'context': context,
            'view_mode': 'form',
            'views': [(self.env.ref('roc_custom.mrp_alternative_product_assistant_wizard_view').id, 'form')],
            'target': 'new',
        }
class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def _get_moves_raw_values(self):
        moves = []
        for production in self:
            if not production.bom_id:
                continue
            factor = production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
            #import pdb;pdb.set_trace()
            for bom_line, line_data in lines:
                if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' or\
                        bom_line.product_id.type not in ['product', 'consu']:
                    continue
                product_id = bom_line.product_id
                if bom_line.match_attributes:
                    final_product_attribute_dict = {}
                    for attribute_line in production.product_id.product_tmpl_id.attribute_line_ids:
                        final_product_attribute_dict[
                            attribute_line.attribute_id.name] = production.product_id.product_template_attribute_value_ids.filtered(
                            lambda x: x.attribute_id.id == attribute_line.attribute_id.id)
                    product_template_id = product_id.product_tmpl_id
                    failed = False
                    for product_variant in product_template_id.product_variant_ids:
                        for attribute, value in final_product_attribute_dict.items():
                            if attribute in product_variant.product_template_attribute_value_ids.mapped('attribute_id.name'):
                                if value.name not in product_variant.product_template_variant_value_ids.mapped('name'):
                                    failed = True
                                    break
                        if not failed:
                            product_id = product_variant
                            break
                        else:
                            continue
                operation = bom_line.operation_id.id or line_data['parent_line'] and line_data['parent_line'].operation_id.id
                moves.append(production._get_move_raw_values(
                    product_id,
                    line_data['qty'],
                    bom_line.product_uom_id,
                    operation,
                    bom_line
                ))
        return moves

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

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    alternative_product_domain = fields.Char(string="Productos Alternativos")
    match_attributes = fields.Boolean(string="Matchear Atributos")

    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id