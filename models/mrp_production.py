from odoo import fields, models, api
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

class MrpAttributeConversionTable(models.Model):
    _name = 'mrp.attribute.conversion.table'

    mrp_product_attribute_name = fields.Char()
    bom_attribute_equivalen_name = fields.Char()

class StockRule(models.Model):
    _inherit = 'stock.rule'
    def _should_auto_confirm_procurement_mo(self, p):
        return False

class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.onchange('product_id', 'location_id')
    def call_get_location_qtys(self):
        self.get_location_qtys()
    def get_location_qtys(self):
        for record in self:
            virtual_qty = record.with_context(
                location=record.location_id.id, compute_child=True
            ).product_id.virtual_available or 0
            qty = record.with_context(
                location=record.location_id.id, compute_child=True
            ).product_id.qty_available_not_res or 0
            record.location_product_virtual_available = virtual_qty
            record.location_product_qty_available_not_res = qty
    location_product_virtual_available = fields.Float(compute=get_location_qtys)
    location_product_qty_available_not_res = fields.Float(compute=get_location_qtys)

    @api.depends('bom_line_id')
    def get_alternative_prod_domain(self):
        for record in self:
            res = []
            if record.bom_line_id:
                if record.bom_line_id.match_attributes:
                    res.insert(0, ('product_tmpl_id', '=', record.bom_line_id.product_id.product_tmpl_id.id))
                    if record.bom_line_id.alternative_product_domain:
                        res.insert(0, '|')
                if record.bom_line_id.force_attributes_value_ids:
                    production_product = record.raw_material_production_id.product_id
                    matching_attr_values = production_product.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in record.bom_line_id.force_attributes_value_ids.mapped('id'))
                    for matching_attrs_value in matching_attr_values:
                        res.insert(0, ('product_template_variant_value_ids.name', 'ilike', matching_attrs_value.name ))
                if record.bom_line_id.alternative_product_domain:
                    res.extend(json.loads(record.bom_line_id.alternative_product_domain))
            record.alternative_product_domain = json.dumps(res)

    alternative_product_domain = fields.Char(compute=get_alternative_prod_domain, store=True)

    def open_alternative_products(self):
        context = {
                'required_attr_name': self.raw_material_production_id.product_id.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in self.bom_line_id.force_attributes_value_ids.mapped('id')).mapped('name') or [],
                'required_attr_ids': self.raw_material_production_id.product_id.product_template_variant_value_ids.filtered(lambda x: x.attribute_id.id in self.bom_line_id.force_attributes_value_ids.mapped('id')).mapped('id') or [],
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

    def action_stand_by(self):
        for record in self:
            record.state = 'stand_by'

    def action_draft(self):
        for record in self:
            record.state = 'draft'


    state = fields.Selection(selection_add=[('stand_by', 'Stand-By')])
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        copied = super(MrpProduction, self).copy(default)
        #for copy in copied:
        #    if self.sale_order_ids:
        #        copy.procurement_group_id = self.procurement_group_id.id
        return copied
    @api.depends('sale_order_ids')
    def get_opportunity(self):
        for record in self:
            res = False
            if record.sale_order_ids and record.sale_order_ids.mapped('opportunity_id'):
                res = record.sale_order_ids.mapped('opportunity_id.id')[0]
            record.opportunity_id = res

    opportunity_id = fields.Many2one('crm.lead', compute=get_opportunity, store=True, string="Oportunidad")

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        #for rec in res:
        #    if rec.sale_order_ids:
        #        group_id = self.env['procurement.group'].create({'move_type': 'direct', 'name': rec.sale_order_ids[0].name - rec.name}).id
        #        res.procurement_group_id = group_id
        return res
    def _get_moves_raw_values(self):
        moves = []
        for production in self:
            if not production.bom_id:
                continue
            factor = production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            final_product = production.product_id
            final_prod_values = final_product.product_template_variant_value_ids
            boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
            for bom_line, line_data in lines:
                product_id = bom_line.product_id
                available_products = bom_line.product_id.product_tmpl_id.product_variant_ids
                if bom_line.default_product_tmpl_ids:
                    available_products += bom_line.default_product_tmpl_ids.mapped('product_variant_ids')
                if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' or\
                        bom_line.product_id.type not in ['product', 'consu']:
                    continue
                if bom_line.force_attributes_value_ids:
                    for forced_att in bom_line.force_attributes_value_ids:
                        alias_final_product_values = final_prod_values.filtered(lambda x: forced_att.name == x.attribute_id.name).mapped('name')
                        alias_final_product_values.extend(self.env['mrp.attribute.conversion.table'].search([('mrp_product_attribute_name', 'in', alias_final_product_values)]).mapped(
                            'bom_attribute_equivalen_name'))
                        available_products = available_products.filtered(lambda x: any(ptvalue in alias_final_product_values for ptvalue in x.product_template_variant_value_ids.mapped('name')))
                if bom_line.match_attributes:
                    for prod in available_products:
                        failed = False
                        for prod_att_value in final_prod_values:
                            alias_final_product_values = prod_att_value.mapped('name')
                            alias_final_product_values.extend(self.env['mrp.attribute.conversion.table'].search(
                                [('mrp_product_attribute_name', 'in', alias_final_product_values)]).mapped(
                                'bom_attribute_equivalen_name'))
                            if not any(alias_final_product_value in prod.product_template_variant_value_ids.mapped('name') for alias_final_product_value in alias_final_product_values):
                                failed = True
                        if not failed:
                            product_id = prod
                            break
                operation = bom_line.operation_id.id or line_data['parent_line'] and line_data['parent_line'].operation_id.id
                moves.append(production._get_move_raw_values(
                    product_id,
                    line_data['qty'],
                    bom_line.product_uom_id,
                    operation,
                    bom_line
                ))
        return moves

    @api.depends('move_raw_ids', 'state', 'move_raw_ids.product_uom_qty')
    def _compute_unreserve_visible(self):
        #adds stand by state
        for order in self:
            already_reserved = order.state not in ('done', 'cancel') and order.mapped('move_raw_ids.move_line_ids')
            any_quantity_done = any(m.quantity_done > 0 for m in order.move_raw_ids)
            order.unreserve_visible = not any_quantity_done and already_reserved
            order.reserve_visible = order.state in ('stand_by','confirmed', 'progress', 'to_close') and any(move.product_uom_qty and move.state in ['confirmed', 'partially_available'] for move in order.move_raw_ids)
    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            name += " | " + dict(rec._fields['state']._description_selection(self.env)).get(rec.state)
            if rec.components_availability:
                name += " | " + rec.components_availability
            res.append((rec.id, name))
        return res
    purchase_order_ids = fields.Many2many(comodel_name='purchase.order', compute='_compute_purchase_order_link', store=True, string="Compras generadas")

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
            production.purchase_order_ids = [(6, 0, po_ids)]

    sale_order_ids = fields.Many2many(comodel_name='sale.order',compute='_compute_sale_order_link', store=True, string="Venta")

    @api.depends('procurement_group_id.mrp_production_ids.move_dest_ids.group_id.sale_id')
    def _compute_sale_order_link(self):
        for production in self:
            so_ids = []
            if production.procurement_group_id and production.procurement_group_id.mrp_production_ids:
                for mrp_prod in production.procurement_group_id.mrp_production_ids:
                    for move in mrp_prod.move_dest_ids:
                        if move.group_id and move.group_id.sale_id:
                            so_ids.append(move.group_id.sale_id.id)
            production.sale_order_ids = [(6, 0, so_ids)]

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    alternative_product_domain = fields.Char(string="Productos Alternativos")
    match_attributes = fields.Boolean(string="Matchear Atributos")
    default_product_tmpl_ids = fields.Many2many('product.template', string="Prod Default")


    @api.depends('bom_id.product_tmpl_id')
    def get_attribute_domain(self):
        for record in self:
            res = [('id', '=', 0)]
            if record.bom_id.product_tmpl_id and record.bom_id.product_tmpl_id.attribute_line_ids:
                res = [('id', 'in', record.bom_id.product_tmpl_id.attribute_line_ids.mapped('attribute_id.id'))]
            record.attribute_values_domain = json.dumps(res)

    attribute_values_domain = fields.Char(compute=get_attribute_domain, store=True)
    force_attributes_value_ids = fields.Many2many('product.attribute', 'aux_attr_mrp_bom_table', 'attribute_value_id', 'bom_line_id', string="Atr. Obligatorios")
    def _get_default_product_uom_id(self):
        return self.env['uom.uom'].search([], limit=1, order='id').id