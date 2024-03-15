from odoo import fields, models, api
import json
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    _order = 'create_date desc'

    @api.constrains('state')
    def constraint_additional_product(self):
        for record in self:
            if record.state not in ('draft', 'cancel') and record.order_line.filtered(lambda x: x.additional_product_required):
                raise UserError("Faltan agregar productos adicionales")
    def open_additional_product_conf(self):
        wiz = self.env['purchase.additional.product.wiz'].create({'purchase_id': self.id})
        sec = 1
        for line in self.order_line:
            line.sequence = sec
            sec += 1

        res = wiz.add_and_continue()
        return res

    @api.depends('order_line', 'order_line.additional_product_done')
    def compute_additional_product_pending(self):
        for record in self:
            if record.order_line.filtered(lambda x: x.additional_product_done != True):
                res = True
            else:
                res = False
            record.additional_product_pending = res
    additional_product_pending = fields.Boolean(compute=compute_additional_product_pending, store=True)
    #visibility_button additional products
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(PurchaseOrderLine, self).create(vals_list)
        order_ids = []
        sec = 0
        for order in lines.mapped('order_id'):
            if order.id in order_ids:
                continue
            else:
                for line in order.order_line:
                    line.sequence = sec
                    sec += 1
                order_ids.append(order.id)
        new_vals = []
        for line in lines:
            if line.orderpoint_id and line.product_id and line.product_id.product_tmpl_id.additional_product_ids:
                for additional_prod in line.product_id.product_tmpl_id.additional_product_ids:
                    if additional_prod.default_product_id:
                        new_vals.append((0, 0, {
                            'display_type': 'line_section',
                            'sequence': line.sequence,
                            'product_qty': 0,
                            'name': additional_prod.name,
                            'additional_purchase_line_parent_id': line.id}))
                        new_vals.append((0, 0, {
                            'product_id': additional_prod.default_product_id.id,
                            'name': additional_prod.default_product_id.name,
                            'sequence': line.sequence,
                            'product_qty': line.product_qty,
                            'additional_purchase_line_parent_id': line.id,
                            'config_id': additional_prod.id}))

            line.order_id.order_line = new_vals
        return lines

    config_id = fields.Many2one('purchase.additional.product')
    additional_purchase_line_parent_id = fields.Many2one('purchase.order.line')
    additional_purchase_line_child_ids = fields.One2many('purchase.order.line', 'additional_purchase_line_parent_id')

    @api.depends('product_template_id', 'product_template_id.additional_product_ids')
    def compute_additional_product_status(self):
        for record in self:
            vals_to_create = []
            if record.product_template_id.additional_product_ids:
                for line in record.product_template_id.additional_product_ids:
                    vals_to_create.append({'purchase_line_id': record.id, 'config_id': line.id})
            self.env['additional.product.status'].create(vals_to_create)
            record.trigger_compute_additional_product_status = False if record.trigger_compute_additional_product_status else True

    trigger_compute_additional_product_status = fields.Boolean(compute=compute_additional_product_status, store=True)
    additional_product_status = fields.One2many('additional.product.status', 'purchase_line_id')

    @api.depends('additional_product_status', 'additional_product_status.matching_lines')
    def compute_additional_product_done(self):
        for record in self:
            res = True
            if record.additional_product_status.filtered(lambda x: not x.matching_lines):
                res = False
            if record.additional_product_status.filtered(lambda x: not x.matching_lines and x.config_id.required):
                record.additional_product_required = True
            else:
                record.additional_product_required = False
            record.additional_product_done = res

    additional_product_done = fields.Boolean(compute=compute_additional_product_done, store=True)
    additional_product_required = fields.Boolean(compute=compute_additional_product_done, store=True)
class ProductTemplate(models.Model):
    _inherit = "product.template"

    additional_product_ids = fields.Many2many('purchase.additional.product')


class PurchaseAdditionalProduct(models.Model):
    _name = "purchase.additional.product"

    name = fields.Char(required=True, string="Nombre")
    required = fields.Boolean(string="Requerido")
    domain = fields.Char(required=True, string="Productos")
    default_product_id = fields.Many2one('product.product')

class AdditionalProductStatus(models.Model):
    _name = "additional.product.status"

    purchase_line_id = fields.Many2one('purchase.order.line')
    config_id = fields.Many2one('purchase.additional.product')
    @api.depends('purchase_line_id.order_id.order_line')
    def compute_matching_lines(self):
        for record in self:
            matching_ids = []
            if record.purchase_line_id and record.config_id:
                lines_to_check = record.purchase_line_id.additional_purchase_line_child_ids.filtered(lambda x: x.config_id.id == record.config_id.id)
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
    already_done_additional_lines = fields.Many2many('additional.product.status')

    additional_product_name = fields.Char(string="Nombre")
    line_ids = fields.One2many('purchase.additional.product.wiz.line', 'wiz_id')
    purchase_id = fields.Many2one('purchase.order')
    po_line = fields.Many2one('purchase.order.line')
    status_id = fields.Many2one('additional.product.status')

    def add_and_continue(self):
        vals_po_write = []
        #adds order_line and section if there are any lines
        if self.line_ids.filtered(lambda x: x.add_product):
            vals_po_write.append((0, 0,
                                  {'display_type': 'line_section',
                                   'sequence': self.po_line.sequence if self.po_line else 10,
                                   'product_qty': 0,
                                   'name': self.status_id.config_id.name if self.status_id else False,
                                   'additional_purchase_line_parent_id': self.po_line.id}))
            for line in self.line_ids.filtered(lambda x: x.add_product):
                vals_po_write.append((0, 0,
                                      {'product_id': line.product_id.id,
                                       'sequence': self.po_line.sequence if self.po_line else 10,
                                       'product_qty': line.qty,
                                       'additional_purchase_line_parent_id': self.po_line.id,
                                       'config_id': self.status_id.config_id.id,}))
            if vals_po_write:
                self.purchase_id.order_line = vals_po_write

        #checks_if_other_config_for_the_current_line
        if self.status_id and self.po_line:
            self.already_done_additional_lines = [(4, self.status_id.id)]
            config_to_process = self.po_line.additional_product_status.filtered(lambda x: not x.has_matching_lines and x.id not in self.already_done_additional_lines.mapped('id'))
            if not config_to_process:
                self.already_done_lines = [(4, self.po_line.id)]

        #loads lines and wiz if something else to proccess
        vals_to_write = {}
        lines_to_process = self.purchase_id.order_line.filtered(lambda x: x.id not in self.already_done_lines.mapped('id') and x.product_template_id.additional_product_ids and x.additional_product_done != True)
        if not lines_to_process:
            return False
        po_line = lines_to_process[0]
        config_to_process = po_line.additional_product_status.filtered(lambda x: not x.has_matching_lines and x.id not in self.already_done_additional_lines.mapped('id'))
        if not config_to_process:
            return False
        config_id = config_to_process[0]

        self.line_ids = [(5,)]
        lines = []
        vals_to_write['po_line'] = po_line.id
        vals_to_write['status_id'] = config_id.id
        products_available = self.env['product.product'].search(json.loads(config_id.config_id.domain))
        vals_to_write['additional_product_name'] = po_line.name + " | " + config_id.config_id.name
        for prod in products_available:
            lines.append((0,0,{'add_product':False, 'product_id': prod.id, 'qty':po_line.product_qty}))
        vals_to_write['line_ids'] = lines
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