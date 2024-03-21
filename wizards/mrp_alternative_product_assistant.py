from odoo import api, fields, models
import json
class MrpAlternativeProductAssistant(models.TransientModel):
    _name = "mrp.alternative.product.assistant"

    see_attributes = fields.Boolean()
    product_production_id = fields.Many2one('product.product', string="Componente a reemplazar")

    match_attributes = fields.Boolean(string="Buscar por atributos")
    filter_by_template = fields.Boolean(string="Buscar por plantilla de producto")
    product_template_ids = fields.Many2many('product.template', string="Plantillas")
    prod_template_domain = fields.Char()

    attribute_value_domain = fields.Char()
    attribute_value_ids = fields.Many2many('product.template.attribute.value', 'aux_table_mrp_wiz_2', 'wiz_id', 'att_value_id', string="Atributos")
    only_available_products = fields.Boolean(string="Solo productos disponibles")

    stock_move_id = fields.Many2one('stock.move')
    product_to_replace = fields.Many2one(related='stock_move_id.product_id')
    bom_line_id = fields.Many2one('mrp.bom.line', related='stock_move_id.bom_line_id')
    line_ids = fields.One2many('mrp.alternative.product.assistant.line', 'wiz_id')
    show_line_ids = fields.Many2many('mrp.alternative.product.assistant.line', 'aux_table_mrp_wiz', 'wiz_id', 'line_id')

    @api.onchange('only_available_products', 'attribute_value_ids', 'product_template_ids')
    def _change_lines(self):
        self.ensure_one()
        lines = self.line_ids
        if self.only_available_products:
            lines = lines.filtered(lambda x: x.location_available > 0 or x.location_virtual_available > 0)
        if self.filter_by_template:
            lines = lines.filtered(lambda x: x.product_id.product_tmpl_id.name in self.product_template_ids.mapped('name'))
        if self.match_attributes:
            failed_line_ids = []
            for attribute_value in self.attribute_value_ids:
                for line in lines:
                    if line.product_id.id not in failed_line_ids:
                        if attribute_value.attribute_id.name in line.product_id.product_template_attribute_value_ids.mapped('attribute_id.name') and attribute_value.name not in line.product_id.product_template_variant_value_ids.mapped('name'):
                            failed_line_ids.append(line.product_id.id)
                            continue
                    else:
                        continue
            lines = lines.filtered(lambda x: x.product_id.id not in failed_line_ids)
        self.show_line_ids = [(6, 0, lines.mapped('id'))]



    @api.model
    def default_get(self, fields):
        """ Allow support of active_id / active_model instead of jut default_lead_id
        to ease window action definitions, and be backward compatible. """
        result = super(MrpAlternativeProductAssistant, self).default_get(fields)
        domain = json.loads(self._context.get('domain', False))
        result['stock_move_id'] = self._context.get('move_id', False)
        result['product_production_id'] = self._context.get('product_production_id', False)
        location = self._context.get('location', False)
        #result['attribute_value_ids'] = [(6, 0, self._context.get('attr_values', []))]
        result['attribute_value_domain'] = json.dumps([('id', 'in', self._context.get('attr_values', []))])
        qty = self._context.get('qty', 1)
        available_products = self.env['product.product'].search(domain)
        #result['product_template_ids'] = [(6, 0, available_products.mapped('product_tmpl_id.id'))]
        result['prod_template_domain'] = json.dumps([('id', 'in', available_products.mapped('product_tmpl_id.id'))])
        lines = []
        for prod in available_products:
            lines.append((0, 0, {
                'product_id': prod.id,
                'qty': qty,
                'location_id': location
            }))
        result['line_ids'] = lines
        result['show_line_ids'] = lines
        return result
    def replace_product(self):
        vals_to_write = []
        #add delete product
        vals_to_write.append((2, self.stock_move_id.id))
        #add product lines
        for line_to_add in self.show_line_ids.filtered(lambda x: x.add_product):
            vals_to_write.append((0, 0, {
                'name': line_to_add.product_id.name,
                'location_id': self.stock_move_id.location_id.id,
                'location_dest_id': self.stock_move_id.location_dest_id.id,
                'product_uom': line_to_add.product_id.uom_id.id,
                'product_id': line_to_add.product_id.id,
                'product_uom_qty': line_to_add.qty,
                'bom_line_id': self.stock_move_id.bom_line_id.id,
            }))
        #write_lines
        self.stock_move_id.raw_material_production_id.write({
            'move_raw_ids': vals_to_write
        })
        return False

class MrpAlternativeProductAssistantLine(models.TransientModel):
    _name = "mrp.alternative.product.assistant.line"

    wiz_id = fields.Many2one('mrp.alternative.product.assistant')
    add_product = fields.Boolean(string="Agregar")

    @api.depends('product_id')
    def get_location_av(self):
        for record in self:
            qty_av = 0
            qty_virt = 0
            if record.product_id:
                qty_av = record.product_id.with_context(
                    location=record.location_id.id, compute_child=True
                ).qty_available
                qty_virt = record.product_id.with_context(
                    location=record.location_id.id, compute_child=True
                ).virtual_available
            record.location_available = qty_av
            record.location_virtual_available = qty_virt

    location_id = fields.Many2one('stock.location', string="De")
    location_available = fields.Float(compute=get_location_av, store=True, string="Disponible")
    location_virtual_available = fields.Float(compute=get_location_av, store=True, string="Pronosticado")
    product_id = fields.Many2one('product.product', string="Producto")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', string="Plantilla Producto")
    product_template_variant_value_ids = fields.Many2many(related='product_id.product_template_variant_value_ids', string="Atributos")
    product_uom = fields.Many2one(related="product_id.uom_id", string="UdM")
    qty = fields.Float(string="Cantidad")