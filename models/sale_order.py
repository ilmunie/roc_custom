from odoo import fields, models, api
import json
class SaleOrder(models.Model):
    _inherit = "sale.order"
    _order = 'create_date desc'



    journal_id = fields.Many2one('account.journal', domain=[('type', '=', 'sale')], string="Diario")
    @api.depends('state', 'order_line', 'order_line.qty_delivered', 'order_line.product_uom_qty')
    def compute_delivery_status(self):
        for record in self:
            if record.state in ('sale', 'done'):
                partial = any(line.qty_delivered > 0 for line in record.order_line)
                full = all(line.qty_delivered >= line.product_uom_qty for line in record.order_line)
                if full:
                    record.delivery_status = 'full_delivery'
                elif partial:
                    record.delivery_status = 'partial_delivery'
                else:
                    record.delivery_status = 'waiting_delivery'
            else:
                record.delivery_status = 'no_confirmed'

    delivery_status = fields.Selection(string='Estado de envío', selection=[('no_confirmed', 'No confirmado'), ('waiting_delivery', 'Esperando entrega'), ('partial_delivery', 'Entrega parcial'), ('full_delivery','Entregado')],store=True, compute=compute_delivery_status)

    door_location = fields.Char(
        string="Ubicación puerta",
    )

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for record in self:
            if record.opportunity_id:
                record.opportunity_id.sync_expected_revenue()
        return res
    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        for record in self:
            if record.opportunity_id:
                record.opportunity_id.sync_expected_revenue()
        return res

    @api.depends('partner_id')
    def get_domain_shipping(self):
        for record in self:
            domain = [('id','=',0)]
            if record.partner_id:
                domain = ['|',('id', '=', record.partner_id.id), ('parent_id', '=', record.partner_id.id)]
            record.shipping_domain_id = json.dumps(domain)

    shipping_domain_id = fields.Char(compute=get_domain_shipping)
    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.partner_id:
                name += " | " + rec.partner_id.name
            name += " | " + dict(rec._fields['state']._description_selection(self.env)).get(rec.state)
            res.append((rec.id, name))
        return res

    product_tmp_id = fields.Many2one(related='order_line.product_template_id', string="Plantilla de producto")
    product_id = fields.Many2one(related='order_line.product_id',string="Variante de producto" )

    @api.depends(
        'procurement_group_id.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids')
    def _compute_mrp_production_rel(self):
        for sale in self:
            data = self.env['procurement.group'].read_group([('sale_id', '=', sale.id)], ['ids:array_agg(id)'],
                                                            ['sale_id'])
            mrp_ids = set()
            for item in data:
                procurement_groups = self.env['procurement.group'].browse(item['ids'])
                mrp_ids |= set(
                    procurement_groups.stock_move_ids.created_production_id.procurement_group_id.mrp_production_ids.ids) | \
                           set(procurement_groups.mrp_production_ids.ids)
            sale.mrp_production_ids = [(6, 0, mrp_ids)]
    mrp_production_ids = fields.Many2many('mrp.production', compute='_compute_mrp_production_rel', store=True)

    @api.depends('order_line.purchase_line_ids.order_id')
    def _compute_purchase_order_rel(self):
        for order in self:
            order.purchase_order_ids = [(6,0,order._get_purchase_orders().mapped('id'))]

    purchase_order_ids = fields.Many2many(comodel_name='purchase.order', compute=_compute_purchase_order_rel,store=True)


    purchase_order_count = fields.Integer(
        "Number of Purchase Order Generated",
        compute='_compute_purchase_order_count',
        groups='purchase.group_purchase_user')

    @api.depends('purchase_order_ids')
    def _compute_purchase_order_count(self):
        for order in self:
            order.purchase_order_count = len(order.purchase_order_ids.mapped('id'))

    def action_view_purchase_orders(self):
        self.ensure_one()
        purchase_order_ids = self.purchase_order_ids.mapped('id')
        action = {
            'res_model': 'purchase.order',
            'type': 'ir.actions.act_window',
        }
        if len(purchase_order_ids) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': purchase_order_ids[0],
            })
        else:
            action.update({
                'name': _("Purchase Order generated from %s", self.name),
                'domain': [('id', 'in', purchase_order_ids)],
                'view_mode': 'tree,form',
            })
        return action