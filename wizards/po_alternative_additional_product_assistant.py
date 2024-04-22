from odoo import api, fields, models
import json
class PoAlternativeAdditionalProductAssistant(models.TransientModel):
    _name = "po.alternative.additional.product.assistant"

    config_id = fields.Many2one('purchase.additional.product')
    line_to_replace_id = fields.Many2one('purchase.order.line')
    line_ids = fields.One2many('po.alternative.additional.product.assistant.line', 'wiz_id')
    seller_id = fields.Many2one('product.supplierinfo')
    parent_poline_id = fields.Many2one(related='line_to_replace_id.additional_purchase_line_parent_id')
    @api.model
    def default_get(self, fields):
        """ Allow support of active_id / active_model instead of jut default_lead_id
        to ease window action definitions, and be backward compatible. """
        result = super(PoAlternativeAdditionalProductAssistant, self).default_get(fields)
        domain = json.loads(self._context.get('domain', False))
        qty = self._context.get('qty', False)
        result['config_id'] = self._context.get('config_id', False)
        result['seller_id'] = self._context.get('seller_id', False)
        result['line_to_replace_id'] = self._context.get('line_to_replace_id', False)
        available_products = self.env['product.product'].search(domain)
        lines = []
        for prod in available_products:
            lines.append((0, 0, {
                'product_id': prod.id,
                'qty': qty,
            }))
        result['line_ids'] = lines
        return result
    def replace_product(self):
        vals_to_write = []
        #add delete product
        vals_to_write.append((2, self.line_to_replace_id.id))
        #add product lines
        for line_to_add in self.line_ids.filtered(lambda x: x.add_product):
            vals = {
                'sequence': self.line_to_replace_id.sequence,
                'name': line_to_add.product_id.name,
                'product_id': line_to_add.product_id.id,
                'product_qty': line_to_add.qty,
                'config_id': self.line_to_replace_id.config_id.id,
                'additional_purchase_line_parent_id': self.line_to_replace_id.additional_purchase_line_parent_id.id
            }
            if line_to_add.price > 0:
                vals['price_unit'] = line_to_add.price
            vals_to_write.append((0, 0, vals))

        self.line_to_replace_id.order_id.write({
            'order_line': vals_to_write
        })
        return False

class PorAlternativeAdditionalProductAssistantLine(models.TransientModel):
    _name = "po.alternative.additional.product.assistant.line"

    @api.depends('product_id')
    def get_price(self):
        for record in self:
            price = 0
            if record.wiz_id.seller_id and record.wiz_id.seller_id.additional_pricelist:
                match_line = record.wiz_id.seller_id.additional_pricelist_ids.filtered(lambda x: x.product_id.id == record.product_id.id)
                price = match_line[0].price if match_line else 0
            if price == 0:
                seller = record.product_id._select_seller(partner_id=record.wiz_id.seller_id.name)
                if seller:
                    price = seller.price
            record.price = price
    price = fields.Float(compute=get_price, store=True, string="Precio")
    wiz_id = fields.Many2one('po.alternative.additional.product.assistant')
    add_product = fields.Boolean(string="Agregar")
    product_id = fields.Many2one('product.product', string="Producto")
    qty = fields.Float(string="Cantidad")
    @api.depends('product_id')
    def get_location_av(self):
        for record in self:
            qty_av = 0
            qty_virt = 0
            qty_not_res = 0
            if record.wiz_id and record.wiz_id.line_to_replace_id and record.wiz_id.line_to_replace_id.order_id and record.wiz_id.line_to_replace_id.order_id.picking_type_id and record.wiz_id.line_to_replace_id.order_id.picking_type_id.default_location_dest_id:
                location_id = record.wiz_id.line_to_replace_id.order_id.picking_type_id.default_location_dest_id.id
            else:
                location_id = self.env.ref('stock.stock_location_locations').id
            if record.product_id:
                qty_av = record.product_id.with_context(
                    location=location_id, compute_child=True
                ).qty_available
                qty_virt = record.product_id.with_context(
                    location=location_id, compute_child=True
                ).virtual_available
                qty_not_res = record.product_id.with_context(
                    location=location_id, compute_child=True
                ).qty_available_not_res
            record.location_id = location_id
            record.location_available = qty_av
            record.location_virtual_available = qty_virt
            record.qty_available_not_res = qty_not_res

    location_id = fields.Many2one('stock.location', string="Ubicación", compute=get_location_av)
    location_available = fields.Float(compute=get_location_av, store=True, string="Disponible")
    qty_available_not_res = fields.Float(compute=get_location_av, store=True, string="No Reservado")
    location_virtual_available = fields.Float(compute=get_location_av, store=True, string="Pronosticado")
