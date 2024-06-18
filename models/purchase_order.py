from odoo import fields, models, api
import json
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    _order = 'create_date desc'

    def action_view_pos_order(self):
        self.ensure_one()
        linked_orders = self.pos_order_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pedidos Punto de venta' if len(linked_orders) > 1 else linked_orders[0].display_name,
            'res_id': linked_orders[0].id,
            'res_model': 'pos.order',
            'view_mode': 'tree,form' if len(linked_orders) > 1 else 'form',
            'domain': [('id', 'in', linked_orders.ids)],
        }



    @api.depends('order_line', 'order_line.move_dest_ids', 'order_line.move_dest_ids.picking_id.pos_order_id')
    def get_pos_order_link(self):
        for record in self:
            pos_ids = []
            for line in record.order_line:
                if line.move_dest_ids:
                    for movedest in line.move_dest_ids:
                        if movedest.picking_id.pos_order_id and movedest.picking_id.pos_order_id.id not in pos_ids:
                            pos_ids.append(movedest.picking_id.pos_order_id.id)
            record.pos_order_count = len(pos_ids)
            record.pos_order_ids = [(6, 0, pos_ids)]
    pos_order_ids = fields.Many2many('pos.order', compute=get_pos_order_link, string="Punto de venta", store=True)
    pos_order_count = fields.Integer(compute=get_pos_order_link, store=True)

    def get_sale_additional_info(self):
        for record in self:
            info = ""
            for production in record.mrp_production_ids:
                info += production.sale_additional_info + "<br/>"
            for pos_order in record.pos_order_ids:
                for line in pos_order.lines.filtered(lambda x: x.customer_note):
                    info += line.product_id.name + " | " + line.customer_note + "<br/>"
            record.sale_additional_info = info
    sale_additional_info = fields.Html(compute=get_sale_additional_info, string="Detalle venta")

    #def button_confirm(self):
    #    for record in self:
    #        for order_line in record.order_line:
    #            order_line.fix_wrong_warehouse_pos()
    #    return super(PurchaseOrder, self)
    @api.depends('sale_order_ids', 'pos_order_ids')
    def get_opportunity(self):
        for record in self:
            res = False
            if record.sale_order_ids and record.sale_order_ids.mapped('opportunity_id'):
                res = record.sale_order_ids.mapped('opportunity_id.id')[0]
            elif record.pos_order_ids and record.pos_order_ids.mapped('opportunity_id'):
                res = record.pos_order_ids.mapped('opportunity_id.id')[0]
            record.opportunity_id = res

    opportunity_id = fields.Many2one('crm.lead', compute=get_opportunity, store=True, string="Oportunidad")

    date_approve = fields.Datetime('Confirmation Date', readonly=False, index=True, copy=False, tracking=True)

    def recreate_picking(self):
        for record in self:
            if record.state in ('done','purchase'):
                record._create_picking()
            else:
                raise UserError('No se puede regenerar las transferencias de un pedido no confirmado')
    @api.onchange('partner_id')
    def onchange_partner_set_picking_type(self):
        for record in self:
            if record.partner_id and record.partner_id.default_purchase_picking_type_id:
                record.picking_type_id = record.partner_id.default_purchase_picking_type_id.id

    delivery_date_status = fields.Selection(string="Coordinación entrega", selection=[('waiting_info','Esperando información'),('date_scheduled','Fecha pactada')],default='waiting_info')
    product_tmp_id = fields.Many2one(related='order_line.product_template_id', string="Plantilla de producto")
    product_id = fields.Many2one(related='order_line.product_id',string="Variante de producto" )
    invoice_number = fields.Char(related='picking_ids.invoice_number', copy=False)
    shipment_number = fields.Char(related='picking_ids.shipment_number', copy=False)
    trigger_compute_rel = fields.Boolean()

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            name += " | " + dict(rec._fields['state']._description_selection(self.env)).get(rec.state)
            name += " | " + dict(rec._fields['reception_status']._description_selection(self.env)).get(rec.reception_status)
            if rec.partner_id:
                name += " | " + rec.partner_id.name
            res.append((rec.id, name))
        return res

    def action_view_mrp(self):
        self.ensure_one()
        linked_orders = self.mrp_production_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ordenes fabricación' if len(linked_orders) > 1 else linked_orders[0].display_name,
            'res_id': linked_orders[0].id,
            'res_model': 'mrp.production',
            'view_mode': 'tree,form' if len(linked_orders) > 1 else 'form',
            'domain': [('id', 'in', linked_orders.ids)],
        }

    @api.depends('order_line.move_dest_ids.group_id.mrp_production_ids','trigger_compute_rel')
    def _compute_mrp_production_link(self):
        for purchase in self:
            mrp_ids = purchase._get_mrp_productions().mapped('id')
            purchase.mrp_production_ids = [(6, 0, mrp_ids)]
            purchase.mrp_production_count = len(mrp_ids)
            purchase.trigger_activity_schedule = True

    mrp_production_ids = fields.Many2many(comodel_name='mrp.production',store=True,compute=_compute_mrp_production_link, string='Órdenes de producción')
    mrp_production_count = fields.Integer(store=True,compute=_compute_mrp_production_link)

    @api.depends('order_line.sale_order_id','order_line.move_dest_ids.group_id.mrp_production_ids','trigger_compute_rel')
    def compute_sale_origin(self):
        for purchase in self:
            sales = purchase._get_sale_orders()
            sale_ids = sales.mapped('id') if sales else []
            for mrp_prod in purchase._get_mrp_productions():
                if mrp_prod.sale_order_ids:
                    sale_ids.extend(mrp_prod.sale_order_ids.mapped('id'))
            purchase.sale_order_ids = [(6, 0, sale_ids)]
            purchase.sale_order_count = len(sale_ids)

    def action_view_so(self):
        self.ensure_one()
        linked_orders = self.sale_order_ids
        return {
            'type': 'ir.actions.act_window',
            'name': 'Ventas' if len(linked_orders) > 1 else linked_orders[0].display_name,
            'res_id': linked_orders[0].id,
            'res_model': 'sale.order',
            'view_mode': 'tree,form' if len(linked_orders) > 1 else 'form',
            'domain': [('id', 'in', linked_orders.ids)],
        }
    sale_order_ids = fields.Many2many(comodel_name='sale.order',store=True,compute=compute_sale_origin, string='Órden Venta')
    sale_order_count = fields.Integer(store=True, compute=compute_sale_origin)
    @api.depends('sale_order_ids','pos_order_ids')
    def compute_partner(self):
        for record in self:
            if record.sale_order_ids:
                record.sale_partner_id = record.sale_order_ids[0].partner_id.id
            elif record.pos_order_ids:
                record.sale_partner_id = record.pos_order_ids[0].partner_id.id
            else:
                record.sale_partner_id = False
    sale_partner_id = fields.Many2one('res.partner',compute=compute_partner,store=True, string='Cliente')

    @api.depends('state', 'order_line', 'order_line.qty_received', 'order_line.product_qty', 'picking_ids', 'picking_ids.state')
    def compute_reception_status(self):
        for record in self:
            if record.state in ('purchase', 'done'):
                partial = any(line.qty_received > 0 for line in record.order_line.filtered(lambda x: x.product_id and x.product_id.detailed_type != 'service'))
                full = all(line.qty_received >= line.product_qty for line in record.order_line.filtered(lambda x: x.product_id and x.product_id.detailed_type != 'service'))
                if full:
                    record.reception_status = 'full_reception'
                elif partial:
                    record.reception_status = 'partial_reception'
                else:
                    record.reception_status = 'waiting_reception'
            else:
                record.reception_status = 'no_confirmed'

    reception_status = fields.Selection(string='Estado de recepción', selection=[('no_confirmed', 'No confirmada'), ('waiting_reception', 'Esperando recepción'), ('partial_reception', 'Recepción parcial'), ('full_reception','Completamente recibida')],store=True, compute=compute_reception_status)
