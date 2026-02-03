from odoo import fields, models, api



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id',  'order_id.picking_type_id.warehouse_id', 'product_id.route_ids')
    def _compute_is_mto(self):
        """ Verify the route of the product based on the warehouse
            set 'is_available' at True if the product availibility in stock does
            not need to be verified, which is the case in MTO, Cross-Dock or Drop-Shipping
        """
        for record in self:
            record.is_mto = False



