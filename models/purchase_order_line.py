from odoo import fields, models, api,_
from collections import defaultdict
from odoo.exceptions import UserError, ValidationError



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_purchase_order_line_from_procurement(self, product_id, product_qty, product_uom, company_id, values, po):
        res = super()._prepare_purchase_order_line_from_procurement(product_id, product_qty, product_uom, company_id, values, po)
        move_dest_ids = values.get('move_dest_ids', False)
        for move in move_dest_ids:
            if move.sale_line_id:
                res['name'] = move.sale_line_id.name
        return res

    def fix_wrong_warehouse_pos(self):
        self.ensure_one()
        if self.order_id.sale_order_ids:
            sale_order = self.order_id.sale_order_ids[0]
            if sale_order.warehouse_id.id != self.order_id.picking_type_id.warehouse_id.id:
                querys = []
                #sale_order.warehouse_id = self.order_id.picking_type_id.warehouse_id.id
                querys.append(f"UPDATE sale_order SET warehouse_id = {str(self.order_id.picking_type_id.warehouse_id.id)} WHERE id = {str(sale_order.id)};")
                for dest_move in self.move_dest_ids:
                    querys.append(
                        f"UPDATE stock_move SET location_id = {str(self.order_id.picking_type_id.warehouse_id.lot_stock_id.id)} WHERE id = {str(dest_move.id)};")
                    #dest_move.location_id = self.order_id.picking_type_id.warehouse_id.lot_stock_id.id
                    querys.append(
                        f"UPDATE stock_picking SET picking_type_id = {str(self.order_id.picking_type_id.warehouse_id.out_type_id.id)} WHERE id = {str(dest_move.picking_id.id)};")
                    querys.append(
                        f"UPDATE stock_picking SET location_id = {str(self.order_id.picking_type_id.warehouse_id.out_type_id.default_location_src_id.id)} WHERE id = {str(dest_move.picking_id.id)};")
                    #dest_move.picking_id.picking_type_id = self.order_id.picking_type_id.warehouse_id.out_type_id.id
                for query in querys:
                    self._cr.execute(query)
    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received', 'product_uom_qty', 'order_id.state', 'trigger_compute_qty_inv', 'product_id.invoice_policy')
    def _compute_qty_invoiced(self):
        for line in self:
            # compute qty_invoiced
            qty = 0.0
            for inv_line in line._get_invoice_lines():
                if inv_line.move_id.state not in ['cancel'] or inv_line.move_id.payment_state == 'invoicing_legacy':
                    if inv_line.move_id.move_type == 'in_invoice':
                        qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.move_id.move_type == 'in_refund':
                        qty -= inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = qty
            if line.order_id.state in ['purchase', 'done']:
                if line.product_id.invoice_policy == 'order':
                    line.qty_to_invoice = line.product_qty - line.qty_invoiced
                else:
                    line.qty_to_invoice = line.qty_received - line.qty_invoiced
            else:
                line.qty_to_invoice = 0

    trigger_compute_qty_inv = fields.Boolean()

    move_ids = fields.One2many('stock.move', 'purchase_line_id', string='Stock Moves')
    product_type = fields.Selection(related='product_id.detailed_type')
    virtual_available_at_date = fields.Float(compute='_compute_qty_at_date', digits='Product Unit of Measure')
    free_qty_today = fields.Float(compute='_compute_qty_at_date', digits='Product Unit of Measure')
    qty_available_today = fields.Float(compute='_compute_qty_at_date')
    scheduled_date = fields.Datetime(compute='_compute_qty_at_date')
    forecast_expected_date = fields.Datetime(compute='_compute_qty_at_date')
    warehouse_id = fields.Many2one(related='order_id.picking_type_id.warehouse_id')
    qty_to_deliver = fields.Float(compute='_compute_qty_to_deliver', digits='Product Unit of Measure')
    is_mto = fields.Boolean(compute='_compute_is_mto')
    display_qty_widget = fields.Boolean(compute='_compute_qty_to_deliver')


    @api.depends(
        'product_id', 'product_uom_qty', 'product_uom', 'date_planned',
        'move_ids', 'move_ids.forecast_expected_date', 'move_ids.forecast_availability')
    def _compute_qty_at_date(self):
        """ Compute the quantity forecasted of product at delivery date. There are
        two cases:
         1. The quotation has a commitment_date, we take it as delivery date
         2. The quotation hasn't commitment_date, we compute the estimated delivery
            date based on lead time"""
        treated = self.browse()
        # If the state is already in sale the picking is created and a simple forecasted quantity isn't enough
        # Then used the forecasted data of the related stock.move
        for line in self.filtered(lambda l: l.state == 'purchase'):
            if not line.display_qty_widget:
                continue
            moves = line.move_ids.filtered(lambda m: m.product_id == line.product_id)
            line.forecast_expected_date = max(moves.filtered("forecast_expected_date").mapped("forecast_expected_date"),
                                              default=False)
            line.qty_available_today = 0
            line.free_qty_today = 0
            for move in moves:
                line.qty_available_today += move.product_uom._compute_quantity(move.reserved_availability, line.product_uom)
                line.free_qty_today += move.product_id.uom_id._compute_quantity(move.forecast_availability,
                                                                                line.product_uom)
            line.scheduled_date = line.date_planned
            line.virtual_available_at_date = False
            treated |= line

        qty_processed_per_product = defaultdict(lambda: 0)
        grouped_lines = defaultdict(lambda: self.env['purchase.order.line'])
        # We first loop over the SO lines to group them by warehouse and schedule
        # date in order to batch the read of the quantities computed field.
        for line in self.filtered(lambda l: l.state in ('draft', 'sent')):
            if not (line.product_id and line.display_qty_widget):
                continue
            grouped_lines[(line.warehouse_id.id, line.date_planned)] |= line

        for (warehouse, scheduled_date), lines in grouped_lines.items():
            product_qties = lines.mapped('product_id').with_context(to_date=scheduled_date, warehouse=warehouse).read([
                'qty_available',
                'free_qty',
                'virtual_available',
            ])
            qties_per_product = {
                product['id']: (product['qty_available'], product['free_qty'], product['virtual_available'])
                for product in product_qties
            }
            for line in lines:
                line.scheduled_date = scheduled_date
                qty_available_today, free_qty_today, virtual_available_at_date = qties_per_product[line.product_id.id]
                line.qty_available_today = qty_available_today - qty_processed_per_product[line.product_id.id]
                line.free_qty_today = free_qty_today - qty_processed_per_product[line.product_id.id]
                line.virtual_available_at_date = virtual_available_at_date - qty_processed_per_product[line.product_id.id]
                line.forecast_expected_date = False
                product_qty = line.product_uom_qty
                if line.product_uom and line.product_id.uom_id and line.product_uom != line.product_id.uom_id:
                    line.qty_available_today = line.product_id.uom_id._compute_quantity(line.qty_available_today,
                                                                                        line.product_uom)
                    line.free_qty_today = line.product_id.uom_id._compute_quantity(line.free_qty_today, line.product_uom)
                    line.virtual_available_at_date = line.product_id.uom_id._compute_quantity(
                        line.virtual_available_at_date, line.product_uom)
                    product_qty = line.product_uom._compute_quantity(product_qty, line.product_id.uom_id)
                qty_processed_per_product[line.product_id.id] += product_qty
            treated |= lines
        remaining = (self - treated)
        remaining.virtual_available_at_date = False
        remaining.scheduled_date = False
        remaining.forecast_expected_date = False
        remaining.free_qty_today = False
        remaining.qty_available_today = False


    @api.depends('product_id',  'order_id.picking_type_id.warehouse_id', 'product_id.route_ids')
    def _compute_is_mto(self):
        """ Verify the route of the product based on the warehouse
            set 'is_available' at True if the product availibility in stock does
            not need to be verified, which is the case in MTO, Cross-Dock or Drop-Shipping
        """
        for record in self:
            record.is_mto = False


    @api.depends('product_type', 'product_uom_qty', 'qty_received', 'state', 'move_ids', 'product_uom')
    def _compute_qty_to_deliver(self):
        """Compute the visibility of the inventory widget."""
        for line in self:
            line.qty_to_deliver = line.product_uom_qty - line.qty_received
            if line.state in ('draft', 'sent', 'purchase') and line.product_type == 'product' and line.product_uom and line.qty_to_deliver > 0:
                if line.state == 'purchase' and not line.move_ids:
                    line.display_qty_widget = False
                else:
                    line.display_qty_widget = True
            else:
                line.display_qty_widget = False




    product_template_id = fields.Many2one(
        'product.template', string='Product Template',
        related="product_id.product_tmpl_id", domain=[('purchase_ok', '=', True)])
    product_updatable = fields.Boolean(compute='_compute_product_updatable', string='Can Edit Product', default=True)
    @api.depends('product_id', 'order_id.state', 'qty_invoiced', 'qty_received')
    def _compute_product_updatable(self):
        for line in self:
            if line.state in ['done', 'cancel'] or (line.state == 'purchase' and (line.qty_invoiced > 0 or line.qty_received > 0)):
                line.product_updatable = False
            else:
                line.product_updatable = True
    product_custom_attribute_value_ids = fields.One2many('product.attribute.custom.value', 'purchase_order_line_id', string="Custom Values POL", copy=True)
    product_no_variant_attribute_value_ids = fields.Many2many('product.template.attribute.value', string="Extra Values", ondelete='restrict')
    is_configurable_product = fields.Boolean('Is the product configurable?', related="product_template_id.has_configurable_attributes")
    product_template_attribute_value_ids = fields.Many2many(related='product_id.product_template_attribute_value_ids', readonly=True)


class ProductAttributeCustomValue(models.Model):
    _inherit = "product.attribute.custom.value"

    purchase_order_line_id = fields.Many2one('purchase.order.line', string="Purchase Order Line", required=True, ondelete='cascade')
    stock_move_id = fields.Many2one('stock.move')
    stock_move_line_id = fields.Many2one('stock.move.line')

    _sql_constraints = [
        ('sol_custom_value_unique', 'unique(custom_product_template_attribute_value_id, purchase_order_line_id)', "Only one Custom Value is allowed per Attribute Value per Sales Order Line.")
    ]