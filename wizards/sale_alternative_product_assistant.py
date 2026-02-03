from odoo import api, fields, models
import json
class SaleAlternativeProductAssistant(models.TransientModel):
    _name = "sale.alternative.product.assistant"

    see_attributes = fields.Boolean()
    sale_template_id = fields.Many2one('sale.order.template')

    match_attributes = fields.Boolean(string="Buscar por atributos")
    filter_by_template = fields.Boolean(string="Buscar por plantilla de producto")
    product_template_ids = fields.Many2many('product.template', string="Plantillas")
    prod_template_domain = fields.Char()

    attribute_alt_value_domain = fields.Char()
    attribute_alt_value_ids = fields.Many2many('product.template.attribute.value', 'aux_table_sale_wiz_3', 'wiz_id', 'att_value_id', string="Atributos alternativos")

    attribute_value_domain = fields.Char()
    attribute_value_ids = fields.Many2many('product.template.attribute.value', 'aux_table_sale_wiz_2', 'wiz_id', 'att_value_id', string="Atributos")
    only_available_products = fields.Boolean(string="Solo productos disponibles")

    sale_line_id = fields.Many2one('sale.order.line')
    product_to_replace = fields.Many2one(related='sale_line_id.product_id')
    sale_template_line_id = fields.Many2one('sale.order.template.line', related='sale_line_id.sale_template_line_id')
    line_ids = fields.One2many('sale.alternative.product.assistant.line', 'wiz_id')
    show_line_ids = fields.Many2many('sale.alternative.product.assistant.line', 'aux_table_sale_wiz', 'wiz_id', 'line_id')

    @api.onchange('only_available_products', 'attribute_value_ids', 'product_template_ids', 'attribute_alt_value_ids')
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
                alternative_names = []
                alternative_names.append(attribute_value.name)
                alternative_names.extend(self.env['sale.attribute.conversion.table'].search(
                    [('mrp_product_attribute_name', '=', attribute_value.name)]).mapped(
                    'bom_attribute_equivalen_name'))
                for line in lines:
                    if line.product_id.id not in failed_line_ids:
                        if (attribute_value.attribute_id.name in line.product_id.product_template_attribute_value_ids.mapped('attribute_id.name') and
                                all(alt_name not in line.product_id.product_template_variant_value_ids.mapped('name') for alt_name in alternative_names)):
                            failed_line_ids.append(line.product_id.id)
                            continue
                    else:
                        continue
            lines = lines.filtered(lambda x: x.product_id.id not in failed_line_ids)
            failed_line_ids = []
            for attribute_value in self.attribute_alt_value_ids:
                for line in lines:
                    if line.product_id.id not in failed_line_ids:
                        if (attribute_value.attribute_id.name in line.product_id.product_template_attribute_value_ids.mapped('attribute_id.name') and
                                attribute_value.name not in line.product_id.product_template_variant_value_ids.mapped('name')):
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
        result = super(SaleAlternativeProductAssistant, self).default_get(fields)
        domain = json.loads(self._context.get('domain', False))
        result['sale_template_id'] = self._context.get('sale_template_id', False)
        result['sale_line_id'] = self._context.get('sale_line_id', False)
        location = self._context.get('location', False)
        result['attribute_value_domain'] = json.dumps([('id', 'in', self._context.get('attr_values', []))])
        qty = self._context.get('qty', 1)
        result['attribute_value_ids'] = [(6, 0, self._context.get('required_attr_ids', []))]
        available_products = self.env['product.product'].search(domain)
        attr_value_name = self._context.get('required_attr_name', [])
        attr_value_add = []
        for prod in available_products:
            for attr_value in prod.mapped('product_template_variant_value_ids'):
                if attr_value.name not in attr_value_name:
                    attr_value_name.append(attr_value.name)
                    attr_value_add.append(attr_value.id)
        result['attribute_alt_value_domain'] = json.dumps([('id', 'in', attr_value_add)])
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
        #if self.show_line_ids:
        selected_prod = self.show_line_ids.filtered(lambda x: x.add_product)
        if selected_prod:
            self.sale_line_id.product_id = selected_prod[0].product_id.id 
            self.sale_line_id.name = selected_prod[0].product_id.name 
            self.sale_line_id.price_unit = selected_prod[0].product_id.list_price
        self.sale_line_id.discount = self.sale_line_id.discount
        return False

class SaleAlternativeProductAssistantLine(models.TransientModel):
    _name = "sale.alternative.product.assistant.line"

    wiz_id = fields.Many2one('sale.alternative.product.assistant')
    add_product = fields.Boolean(string="Agregar")

    location_id = fields.Many2one('stock.location', string="De")

    product_id = fields.Many2one('product.product', string="Producto")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', store=True, string="Plantilla Producto")
    product_template_variant_value_ids = fields.Many2many(related='product_id.product_template_variant_value_ids', store=False, string="Atributos")
    product_uom = fields.Many2one(related="product_id.uom_id", store=True, string="UdM")
    product_category = fields.Many2one(related="product_id.categ_id", store=True)
    list_price = fields.Float(related="product_id.lst_price", store=True)
    qty = fields.Float(string="Cantidad")

    # 🚀 STOCK STOREADO — ya no compute
    location_available = fields.Float(string="Disponible", store=True)
    qty_available_not_res = fields.Float(string="No Reservado", store=True)
    location_virtual_available = fields.Float(string="Pronosticado", store=True)

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)

        domain = json.loads(self._context.get('domain', False))
        result['sale_template_id'] = self._context.get('sale_template_id')
        result['sale_line_id'] = self._context.get('sale_line_id')

        location = self._context.get('location')
        qty = self._context.get('qty', 1)

        available_products = self.env['product.product'].search(domain)
        product_ids = available_products.ids

        # -----------------------
        # 🔥 SQL STOCK BATCH
        # -----------------------
        stock_map = {}

        if product_ids and location:
            query = """
                SELECT product_id,
                       SUM(quantity) AS qty_available,
                       SUM(quantity - reserved_quantity) AS qty_available_not_res
                FROM stock_quant
                WHERE product_id = ANY(%s)
                AND location_id = %s
                GROUP BY product_id
            """
            self.env.cr.execute(query, (product_ids, location))
            for pid, qty_av, qty_not_res in self.env.cr.fetchall():
                stock_map[pid] = {
                    'qty_available': qty_av or 0,
                    'qty_available_not_res': qty_not_res or 0,
                    'virtual_available': qty_av or 0,
                }

        # -----------------------
        # ATRIBUTOS DOMINIOS
        # -----------------------
        attr_value_name = self._context.get('required_attr_name', [])
        attr_value_add = []

        for prod in available_products:
            for attr_value in prod.product_template_variant_value_ids:
                if attr_value.name not in attr_value_name:
                    attr_value_name.append(attr_value.name)
                    attr_value_add.append(attr_value.id)

        result['attribute_value_domain'] = json.dumps([
            ('id', 'in', self._context.get('attr_values', []))
        ])
        result['attribute_value_ids'] = [(6, 0, self._context.get('required_attr_ids', []))]
        result['attribute_alt_value_domain'] = json.dumps([('id', 'in', attr_value_add)])

        result['prod_template_domain'] = json.dumps([
            ('id', 'in', available_products.mapped('product_tmpl_id.id'))
        ])

        # -----------------------
        # 🔥 CREAR LINEAS (STOCK YA CARGADO)
        # -----------------------
        lines = []

        for prod in available_products:
            stock = stock_map.get(prod.id, {})
            lines.append((0, 0, {
                'product_id': prod.id,
                'qty': qty,
                'location_id': location,

                # ⚡ Guardado definitivo
                'location_available': stock.get('qty_available', 0),
                'qty_available_not_res': stock.get('qty_available_not_res', 0),
                'location_virtual_available': stock.get('virtual_available', 0),
            }))

        result['line_ids'] = lines
        result['show_line_ids'] = lines

        return result

@api.onchange('only_available_products', 'attribute_value_ids', 'product_template_ids', 'attribute_alt_value_ids')
def _change_lines(self):
    self.ensure_one()
    lines = self.line_ids

    if self.only_available_products:
        lines = lines.filtered(lambda x: x.location_available > 0 or x.location_virtual_available > 0)

    if self.filter_by_template:
        template_names = set(self.product_template_ids.mapped('name'))
        lines = lines.filtered(lambda x: x.product_tmpl_id.name in template_names)

    if self.match_attributes:
        failed_ids = set()

        for attribute_value in self.attribute_value_ids:
            alt_names = [attribute_value.name]
            alt_names += self.env['sale.attribute.conversion.table'].search([
                ('mrp_product_attribute_name', '=', attribute_value.name)
            ]).mapped('bom_attribute_equivalen_name')

            for line in lines:
                if line.product_id.id in failed_ids:
                    continue

                attr_names = line.product_id.product_template_attribute_value_ids.mapped('attribute_id.name')
                variant_names = line.product_id.product_template_variant_value_ids.mapped('name')

                if attribute_value.attribute_id.name in attr_names and not any(n in variant_names for n in alt_names):
                    failed_ids.add(line.product_id.id)

        lines = lines.filtered(lambda x: x.product_id.id not in failed_ids)

    self.show_line_ids = [(6, 0, lines.ids)]
