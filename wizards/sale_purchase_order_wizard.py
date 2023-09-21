from odoo import api, fields, models, SUPERUSER_ID, _
from datetime import datetime


class SalePurchaseOrderWizard(models.TransientModel):
    _name = 'sale.purchase.order.wizard'

    partner_id = fields.Many2one('res.partner', string='Proveedor', required=True)
    date_order = fields.Datetime(string='Fecha límite', required=True, copy=False, default=fields.Datetime.now)
    sale_id = fields.Many2one('sale.order')
    line_ids = fields.One2many('sale.purchase.order.wizard.line','wiz_id')
    @api.model
    def default_get(self, fields):

        """ Allow support of active_id / active_model instead of jut default_lead_id
        to ease window action definitions, and be backward compatible. """
        result = super(SalePurchaseOrderWizard, self).default_get(fields)
        sale_order = self.env['sale.order'].browse(self._context.get('active_ids', []))
        result['sale_id'] = sale_order.id
        lines = []
        for line in sale_order.order_line:
            lines.append((0, 0, {
                'product_id': line.product_id.id,
                'product_uom': line.product_uom.id,
                'order_id': line.order_id.id,
                'name': line.name,
                'product_qty': line.product_uom_qty,
                'price_unit': line.price_unit,
                'product_subtotal': line.price_subtotal,
                'sale_line_id': line.id
            }))
        result['line_ids'] = lines
        return result
    def action_create_purchase_order(self):
        self.ensure_one()
        res = self.env['purchase.order'].browse(self._context.get('id', []))
        value = []
        so = self.env['sale.order'].browse(self._context.get('active_id'))
        sale_order_name = so.name
        for data in self.line_ids:
            value.append([0, 0, {
                'product_id': data.product_id.id,
                'name': data.name,
                'product_qty': data.product_qty,
                'order_id': data.order_id.id,
                'product_uom': data.product_uom.id,
                'date_planned': data.date_planned,
                'sale_line_id': data.sale_line_id.id
            }])
        if self.partner_id.property_purchase_currency_id :
            currency_id = self.partner_id.property_purchase_currency_id.id
        else:
            currency_id = self.env.company.currency_id.id
        purchase_order = res.create({
            'partner_id': self.partner_id.id,
            'date_order': str(self.date_order),
            'order_line': value,
            'origin': sale_order_name,
            'partner_ref': sale_order_name,
            'currency_id': currency_id,
        })
        if purchase_order.partner_id.property_account_position_id :
            purchase_order.update({'fiscal_position_id':purchase_order.partner_id.property_account_position_id.id})
        message = '<a href="#" data-oe-id=' + str(
            purchase_order.id) + ' data-oe-model="purchase.order">@' + purchase_order.name + '</a>'
        so.message_post(body=message)

        return res
class SalePurchaseOrderWizLine(models.TransientModel):
    _name = 'sale.purchase.order.wizard.line'
    wiz_id = fields.Many2one('sale.purchase.order.wizard')
    sale_line_id = fields.Many2one('sale.order.line')
    product_id = fields.Many2one('product.product', string="Product", required=True)
    name = fields.Char(string="Description")
    product_qty = fields.Float(string='Quantity', required=True)
    date_planned = fields.Datetime(string='Scheduled Date', default=datetime.today())
    product_uom = fields.Many2one('uom.uom', string='Product Unit of Measure')
    order_id = fields.Many2one('sale.order', string='Order Reference', ondelete='cascade', index=True)
    price_unit = fields.Float(string='Unit Price', digits='Product Price')
    product_subtotal = fields.Float(string="Sub Total", compute='_compute_total')
    @api.depends('product_qty', 'price_unit')
    def _compute_total(self):
        for record in self:
            record.product_subtotal = record.product_qty * record.price_unit
