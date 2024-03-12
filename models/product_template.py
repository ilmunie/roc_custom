from odoo import fields, models, api
import json
class ProductTemplate(models.Model):
    _inherit = "product.template"

    additional_product_ids = fields.Many2many('purchase.additional.product')


class PurchaseAdditionalProduct(models.Model):
    _name = "purchase.additional.product"

    name = fields.Char(required=True, string="Nombre")
    required = fields.Boolean(string="Requerido")
    domain = fields.Char(required=True, string="Productos")

class AdditionalProductStatus(models.Model):
    _name = "additional.product.status"

    purchase_line_id = fields.Many2one('purchase.order.line')
    config_id = fields.Many2one('purchase.additional.product')
    @api.depends('purchase_line_id.order_id.order_line')
    def compute_matching_lines(self):
        for record in self:
            matching_ids = []
            if record.purchase_line_id and record.config_id:
                lines_to_check = record.purchase_line_id.order_id.order_line.filtered(lambda x: x.id != record.purchase_line_id.id and x.product_id)
                for line in lines_to_check:
                    domain = json.loads(record.config_id.domain)
                    domain.insert(0, ('id', '=', line.product_id.id))
                    if self.env['product.product'].search(domain):
                        matching_ids.append(line.id)
            record.matching_lines = [(6,0, matching_ids)]
            record.has_matching_lines = True if matching_ids else False

    matching_lines = fields.Many2many('purchase.order.line', compute=compute_matching_lines, store=True)
    has_matching_lines = fields.Boolean(compute=compute_matching_lines, store=True)
    required = fields.Boolean(related='config_id.required')



class PurchaseAdditionalProductWizard(models.TransientModel):
    _name = "purchase.additional.product.wiz"

    already_done_lines = fields.Many2many('purchase.order.line')
    already_done_additional_lines = fields.Many2many('purchase.additional.product')

    additional_product_name = fields.Char(string="Nombre")

    line_ids = fields.One2many('purchase.additional.product.wiz.line', 'wiz_id')
    purchase_id = fields.Many2one(
        'purchase.order')

    def add_and_continue(self):
        vals_po_write = []
        for line in self.line_ids.filtered(lambda x: x.add_product):
            vals_po_write.append((0,0,{'product_id': line.product_id.id, 'product_qty':line.qty}))
        if vals_po_write:
            self.purchase_id.order_line = vals_po_write
        vals_to_write = {}
        self.line_ids = [(5,)]
        lines = []
        pending_po_lines = self.purchase_id.order_line.filtered(lambda x: not x.additional_product_done and x.id not in self.already_done_lines.mapped('id'))
        pending_line_additional_product = False
        #import pdb;pdb.set_trace()
        for po_line in pending_po_lines:
            pending_line_additional_product = po_line.additional_product_status.filtered(lambda x: not x.has_matching_lines and x.config_id.id not in self.already_done_additional_lines.mapped('id')).mapped('config_id')
            if not pending_line_additional_product:
                vals_to_write['already_done_lines'] = [(4, po_line.id)]
            else:
                break
        if pending_line_additional_product:
            for additional_line in pending_line_additional_product:
                products_available = self.env['product.product'].search(json.loads(additional_line.domain))
                vals_to_write['additional_product_name'] = po_line.name + " | " + additional_line.name
                lines = []
                for prod in products_available:
                    lines.append((0,0,{'add_product':False, 'product_id': prod.id, 'qty':po_line.product_qty}))
                vals_to_write['line_ids'] = lines
                vals_to_write['already_done_additional_lines'] = [(4, additional_line.id)]
        self.write(vals_to_write)
        if lines:
            return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.additional.product.wiz',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(self.env.ref('roc_custom.view_purchase_additional_product_wiz').id, 'form')],
            'target': 'new',
            }
        else:
            return False
class PurchaseAdditionalProductWizardLine(models.TransientModel):
    _name = "purchase.additional.product.wiz.line"

    wiz_id = fields.Many2one('purchase.additional.product.wiz')

    add_product = fields.Boolean(string="Agregar producto")
    product_id = fields.Many2one('product.product', string="Producto")
    product_uom = fields.Many2one(related="product_id.uom_id", string="UdM")
    qty = fields.Float(string="Cantidad")