import pdb

from odoo import fields, models, api
import json
from odoo.exceptions import UserError

class ProductSupplierinfo(models.Model):
    _inherit = "product.supplierinfo"

    additional_pricelist = fields.Boolean(string="Tarifas adicionales")
    additional_pricelist_ids = fields.One2many('additional.supplierinfo', 'supplierinfo_id', copy=True)

    @api.depends('product_tmpl_id', 'product_tmpl_id.additional_product_ids', 'product_tmpl_id.additional_product_ids.domain')
    def get_additional_product_domain(self):
        product_model = self.env['product.product']
        for record in self:
            products_av = []
            if record.product_tmpl_id and record.product_tmpl_id.additional_product_ids:
                for add in record.product_tmpl_id.additional_product_ids:
                    products_av.extend(product_model.search(json.loads(add.domain)).mapped('id'))
            record.product_domain = json.dumps([('id', 'in', products_av)])

    product_domain = fields.Char(compute=get_additional_product_domain, store=True)
    @api.depends('product_id','product_tmpl_id')
    def compute_see_aditional_pricelist(self):
        for record in self:
            if record.product_tmpl_id and record.product_tmpl_id and record.product_tmpl_id.additional_product_ids:
                res = True
            else:
                res = False
            record.see_additional_pricelist = res
    see_additional_pricelist = fields.Boolean(compute=compute_see_aditional_pricelist, store=True)
class AdditionalSupplierinfo(models.Model):
    _name = "additional.supplierinfo"

    supplierinfo_id = fields.Many2one('product.supplierinfo')
    product_id = fields.Many2one('product.product', string='Producto')
    price = fields.Float(string="Precio")
    product_domain = fields.Char(related='supplierinfo_id.product_domain')
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    _order = 'create_date desc'

    def compute_requires_additional_products(self):
        for record in self:
            res = False
            if record.order_line.filtered(lambda x: x.product_id.product_tmpl_id.additional_product_ids):
                res = True
            record.requires_additional_products = res

    requires_additional_products = fields.Boolean(compute=compute_requires_additional_products)
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        copied = super(PurchaseOrder, self).copy(default)
        for copy in copied:
            vals = []
            for line_to_del in copy.order_line.filtered(lambda x: x.additional_purchase_line_parent_id):
                vals.append((2, line_to_del.id))
            copy.order_line = vals
        return copied
    def load_default_additional_products(self):
        for record in self:
            #removes old additional lines
            vals = []
            for line_to_del in record.order_line.filtered(lambda x: x.additional_purchase_line_parent_id):
                vals.append((2, line_to_del.id))
            record.order_line = vals
            #add_default_products
            vals = []
            sequence = 1
            for line in record.order_line.filtered(lambda x: x.product_id.product_tmpl_id.additional_product_ids):
                sequence += 1
                vals.append((1, line.id, {'sequence': sequence}))
                seller = line.product_id._select_seller(partner_id=record.partner_id)
                additional_prices = False
                if seller and seller.additional_pricelist and seller.additional_pricelist_ids:
                    additional_prices = seller.additional_pricelist_ids
                for additional_prod in line.product_id.product_tmpl_id.additional_product_ids:
                    if additional_prod.default_product_ids:
                        sequence += 1
                        product_to_add = additional_prod.get_product_to_add(location=record.picking_type_id.default_location_dest_id.id)
                        if product_to_add:
                            vals.append((0, 0, {
                                'display_type': 'line_section',
                                'sequence': sequence,
                                'product_qty': 0,
                                'name': additional_prod.name,
                                'additional_purchase_line_parent_id': line.id}))
                            aux_vals = {
                                'product_id': product_to_add.id,
                                'name': product_to_add.name,
                                'sequence': sequence,
                                'product_qty': line.product_qty*additional_prod.qty,
                                'additional_purchase_line_parent_id': line.id,
                                'config_id': additional_prod.id}
                            if additional_prices and product_to_add.id in additional_prices.mapped('product_id.id'):
                                aux_vals['price_unit'] = additional_prices.filtered(lambda x: x.product_id.id == product_to_add.id)[0].price
                                aux_vals['discount'] = seller.discount
                            else:
                                seller = product_to_add._select_seller(partner_id=record.partner_id)
                                if seller:
                                    aux_vals['price_unit'] = seller.price
                                    aux_vals['discount'] = seller.discount
                            vals.append((0, 0, aux_vals))
            record.order_line = vals


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

    def open_change_additional_product(self):
        seller = self.additional_purchase_line_parent_id.product_id._select_seller(self.order_id.partner_id)
        context = {
            'domain': self.config_id.domain,
            'qty': self.product_qty,
            'config_id': self.config_id.id,
            'line_to_replace_id': self.id,
            'seller_id': seller.id,
        }
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'po.alternative.additional.product.assistant',
            'context': context,
            'view_mode': 'form',
            'views': [(self.env.ref('roc_custom.po_alternative_additional_product_assistant_wizard_view').id, 'form')],
            'target': 'new',
        }
    @api.model_create_multi
    def create(self, vals_list):
        lines = super(PurchaseOrderLine, self).create(vals_list)
        order_ids = []
        sec = 0
        for order in lines.filtered(lambda x: not x.additional_purchase_line_parent_id).mapped('order_id'):
            if order.id in order_ids:
                continue
            else:
                for line in order.order_line:
                    line.sequence = sec
                    sec += 1
                order_ids.append(order.id)
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

class ProductCategory(models.Model):
    _inherit = "product.category"

    material_rentability_multiplier = fields.Float(string="Rentabilidad costo materiales")

class ProductTemplate(models.Model):
    _inherit = "product.template"

    def get_material_rentability_multiplier(self):
        self.ensure_one()
        if self.material_rentability_multiplier > 0:
            return self.material_rentability_multiplier
        if self.categ_id.material_rentability_multiplier > 0:
            return self.categ_id.material_rentability_multiplier
        parent_categ = self.categ_id.parent_id
        while parent_categ:
            if parent_categ.material_rentability_multiplier > 0:
                return parent_categ.material_rentability_multiplier
            parent_categ = parent_categ.parent_id
        return self.env.user.company_id.material_rentability_multiplier

    additional_product_ids = fields.Many2many('purchase.additional.product')
    pos_force_ship_later = fields.Boolean(string="Punto Venta: forzar enviar más tarde")

    price_from_seller = fields.Boolean(string="Precio de venta según costo")

    material_rentability_multiplier = fields.Float(string="Rentabilidad costo materiales")

    #METHOD THAT WRITES STANDARD COST AND (IF CONFIGURED IN PRODUCT) THE SALE PRICE AND EXTRA OF ATTRS
    @api.depends('price_from_seller', 'material_rentability_multiplier', 'categ_id.material_rentability_multiplier', 'seller_ids', 'seller_ids.price', 'seller_ids.variant_extra_ids', 'seller_ids.variant_extra_ids.extra_amount', 'seller_ids.discount', 'price_from_seller')
    def compute_list_price_from_sellers(self):
        for record in self:
            rentability_multiplier = record.get_material_rentability_multiplier()
            if record.price_from_seller:
                sellers = self.seller_ids.filtered(lambda x: x.price > 0)
                sorted_sellers = sorted(sellers, key=lambda r: r.price*(1 - r.discount/100), reverse=True)
                seller = sorted_sellers[0] if sellers else False
                if seller:
                    final_cost = seller.price*(1 - seller.discount/100)
                    record.standard_price = final_cost
                    record.list_price = final_cost*rentability_multiplier
                    if seller.has_extras or seller.variant_extra_ids:
                        for attr_value in record.attribute_line_ids.mapped('product_template_value_ids'):
                            extra_line = seller.variant_extra_ids.filtered(
                                lambda x: attr_value.product_attribute_value_id.display_name in x.attribute_ids.mapped(
                                    'display_name'))
                            if extra_line:
                                price_extra = extra_line[0].extra_amount
                                attr_value.price_extra = rentability_multiplier*price_extra*(1 - seller.discount/100)
            record.trigger_list_price = False if record.trigger_list_price else True


    trigger_list_price = fields.Boolean(compute=compute_list_price_from_sellers, store=True)

class PurchaseAdditionalProduct(models.Model):
    _name = "purchase.additional.product"

    name = fields.Char(required=True, string="Nombre")
    required = fields.Boolean(string="Requerido")
    domain = fields.Char(required=True, string="Productos")
    default_product_ids = fields.Many2many('product.product')
    qty = fields.Float(default=1, string="Cantidad")

    def get_related_prod(self):
        for record in self:
            products = self.env['product.template'].search([('additional_product_ids','!=', False), ('additional_product_ids.id','=', record.id)])
            record.related_products = [(6, 0, products.mapped('id'))]
            record.count_rel_prod = len(products)
    related_products = fields.Many2many('product.template', compute=get_related_prod)
    count_rel_prod = fields.Integer(compute=get_related_prod)

    def see_affected_prod(self):
        return {
            'name': "Productos con adicionales - " + self.name + str(self.id),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'domain': [('additional_product_ids', '!=', False), ('additional_product_ids.id', '=', self.id)],
            'view_mode': 'tree,form',
            'target': 'new',
            'search_view_id': self.env.ref('product.product_template_search_view').id,
        }

    def get_product_to_add(self, location=False):
        min_stock_prod = False
        min_stock = 999999999999999999
        for product in self.default_product_ids:
            product_qty_in_loc = product.with_context(location=location, compute_child=True).virtual_available
            if product_qty_in_loc < min_stock:
                min_stock = product_qty_in_loc
                min_stock_prod = product
        return min_stock_prod

class ProductTemplateAttributeLine(models.Model):
    """Attributes available on product.template with their selected values in a m2m.
    Used as a configuration model to generate the appropriate product.template.attribute.value"""

    _inherit = "product.template.attribute.line"
    _order = 'sequence'

    sequence = fields.Integer(string="Sequencia")

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