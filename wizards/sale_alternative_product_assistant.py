from odoo import api, fields, models
import json


class SaleAlternativeProductAssistant(models.TransientModel):
    _name = "sale.alternative.product.assistant"

    @api.model
    def create_wizard_from_sale_line(self, sale_line, domain, location, qty):
        cr = self.env.cr
        domain = json.loads(domain) if domain else []
    
        Product = self.env['product.product']
    
        # -----------------------------------------
        # Convertir DOMAIN → SQL seguro (Odoo)
        # -----------------------------------------
        query = Product._search(domain, offset=0, limit=None, order=None, count=False)
        from_clause, where_clause, where_params = query.get_sql()
    
        # -----------------------------------------
        # Crear wizard vacío primero
        # -----------------------------------------
        wiz = self.env['sale.alternative.product.assistant'].create({
            'sale_template_id': sale_line.order_id.sale_order_template_id.id,
            'sale_line_id': sale_line.id,
            'see_attributes': True, 
            'prod_template_domain': '[]',
        })
    
        # -----------------------------------------
        # INSERT MASIVO SQL (20k filas sin Python)
        # -----------------------------------------
        sql = f"""
            WITH products AS (
                SELECT product_product.id, product_product.product_tmpl_id
                FROM {from_clause.replace('"','')}
                WHERE {where_clause.replace('"','')}
            ),

            stock AS (
                SELECT 
                    q.product_id,
                    SUM(q.quantity) AS qty_available,
                    SUM(q.quantity - q.reserved_quantity) AS qty_available_not_res
                FROM stock_quant q
                WHERE q.location_id = %s
                GROUP BY q.product_id
            ),

            price_extra AS (
                SELECT 
                    pvc.product_product_id,
                    COALESCE(SUM(ptav.price_extra), 0) AS price_extra
                FROM product_variant_combination pvc
                JOIN product_template_attribute_value ptav
                    ON ptav.id = pvc.product_template_attribute_value_id
                GROUP BY pvc.product_product_id
            )

            INSERT INTO sale_alternative_product_assistant_line (
                visible,
                product_tmpl_id,
                wiz_id,
                product_id,
                qty,
                location_id,
                location_available,
                qty_available_not_res,
                location_virtual_available,

                product_category,
                product_uom,
                list_price,

                create_uid,
                create_date,
                write_uid,
                write_date
            )
            SELECT
                TRUE, 
                p.product_tmpl_id AS product_tmpl_id,
                %s AS wiz_id,
                p.id AS product_id,
                %s AS qty,
                %s AS location_id,

                COALESCE(s.qty_available, 0),
                COALESCE(s.qty_available_not_res, 0),
                COALESCE(s.qty_available, 0),

                pt.categ_id,
                pt.uom_id,
                pt.list_price + COALESCE(pe.price_extra, 0),

                %s, NOW(),
                %s, NOW()

            FROM products p
            JOIN product_template pt 
                ON pt.id = p.product_tmpl_id

            LEFT JOIN stock s 
                ON s.product_id = p.id

            LEFT JOIN price_extra pe
                ON pe.product_product_id = p.id
        """

    
        params = where_params + [
            location,      # stock CTE
            wiz.id,        # wiz_id insert
            qty,           # qty
            location,      # location_id
            self.env.uid,  # create_uid
            self.env.uid,  # write_uid
        ]
    
        cr.execute(sql, params)
    
        cr.execute(f"""
            SELECT 
                ARRAY_AGG(DISTINCT product_product__product_tmpl_id.id),
                ARRAY_AGG(DISTINCT product_product__product_tmpl_id.categ_id)
            FROM {from_clause.replace('"','')}
            WHERE {where_clause.replace('"','')}
        """, where_params)
    
        template_ids, categ_ids = cr.fetchone()
    
        wiz.prod_template_domain = json.dumps([
            ('id', 'in', template_ids)
        ])
        wiz.categ_domain = json.dumps([
            ('id', 'in', categ_ids)
        ])
        # -----------------------------------------
        # ATRIBUTOS ALTERNATIVOS (DISTINCT NAME → IDS)
        # -----------------------------------------
        cr.execute(f"""
            SELECT ARRAY_AGG(sub.id)
            FROM (
                SELECT MIN(ptav.id) AS id
                FROM {from_clause.replace('"','')}
                JOIN product_variant_combination pvc 
                    ON pvc.product_product_id = product_product.id
                JOIN product_template_attribute_value ptav 
                    ON ptav.id = pvc.product_template_attribute_value_id
                JOIN product_attribute_value pav
                            ON pav.id = ptav.product_attribute_value_id
                WHERE {where_clause.replace('"','')}
                GROUP BY pav.name
            ) sub
        """, where_params)

        (attr_ids,) = cr.fetchone()

        wiz.attribute_alt_value_domain = json.dumps([
            ('id', 'in', attr_ids or [])
        ])
        return wiz



    see_attributes = fields.Boolean()
    sale_template_id = fields.Many2one('sale.order.template')
    filter_by_category = fields.Boolean(string="Buscar por categoria")
    product_categ_ids = fields.Many2many('product.category', string="Categorias")
    categ_domain = fields.Char()
    filter_by_template = fields.Boolean(string="Buscar por plantilla de producto")
    product_template_ids = fields.Many2many('product.template', string="Plantillas")
    prod_template_domain = fields.Char()
    match_attributes = fields.Boolean(string="Buscar por atributos")
    attribute_alt_value_domain = fields.Char()
    attribute_alt_value_ids = fields.Many2many('product.template.attribute.value', 'aux_table_sale_wiz_3', 'wiz_id', 'att_value_id', string="Atributos alternativos")
    attribute_value_domain = fields.Char()
    attribute_value_ids = fields.Many2many('product.template.attribute.value', 'aux_table_sale_wiz_2', 'wiz_id', 'att_value_id', string="Atributos")
    only_available_products = fields.Boolean(string="Solo productos disponibles")
    sale_line_id = fields.Many2one('sale.order.line')
    product_to_replace = fields.Many2one(related='sale_line_id.product_id')
    sale_template_line_id = fields.Many2one('sale.order.template.line', related='sale_line_id.sale_template_line_id')
    line_ids = fields.One2many('sale.alternative.product.assistant.line', 'wiz_id', domain=[('visible', '=', True)])
    

    def apply_filters(self):
        self.ensure_one()
        cr = self.env.cr
        wiz_id = self.id
        # Filtros activos
        categ_ids = self.product_categ_ids.ids if self.product_categ_ids else []
        tmpl_ids = self.product_template_ids.ids if self.product_template_ids else []
        selected_attr_ids = self.attribute_alt_value_ids.ids if self.attribute_alt_value_ids else []

        only_available = self.only_available_products
        where = ["wiz_id = %s"]
        params = [wiz_id]
        # -----------------------
        # FILTRO CATEGORÍAS
        # -----------------------
        if categ_ids:
            where.append("product_category = ANY(%s)")
            params.append(categ_ids)
        # -----------------------
        # FILTRO PLANTILLAS
        # -----------------------
        if tmpl_ids:
            where.append("product_tmpl_id = ANY(%s)")
            params.append(tmpl_ids)
        # -----------------------
        # FILTRO STOCK DISPONIBLE
        # -----------------------
        if only_available:
            where.append("qty_available_not_res > 0")
        # -----------------------
        # FILTRO ATRIBUTOS AND (TODOS)
        # -----------------------
        if selected_attr_ids:
            cr.execute("""
                SELECT ARRAY_AGG(DISTINCT pav.name)
                FROM product_template_attribute_value ptav
                JOIN product_attribute_value pav 
                    ON pav.id = ptav.product_attribute_value_id
                WHERE ptav.id = ANY(%s)
            """, [selected_attr_ids])
        
            (attr_name_filter,) = cr.fetchone()
        
            if attr_name_filter:
                where.append("""
                    (
                        SELECT COUNT(DISTINCT pav.name)
                        FROM product_variant_combination pvc
                        JOIN product_template_attribute_value ptav 
                            ON ptav.id = pvc.product_template_attribute_value_id
                        JOIN product_attribute_value pav 
                            ON pav.id = ptav.product_attribute_value_id
                        WHERE pvc.product_product_id = sale_alternative_product_assistant_line.product_id
                          AND pav.name = ANY(%s)
                    ) = %s
                """)
                params.append(attr_name_filter)
                params.append(len(attr_name_filter))

        where_clause = " AND ".join(where)
        # -----------------------
        # 1️⃣ Ocultar todo
        # -----------------------
        cr.execute("""
            UPDATE sale_alternative_product_assistant_line
            SET visible = FALSE
            WHERE wiz_id = %s
        """, [wiz_id])

        # -----------------------
        # 2️⃣ Mostrar solo lo filtrado
        # -----------------------
        sql = f"""
            UPDATE sale_alternative_product_assistant_line
            SET visible = TRUE
            WHERE {where_clause}
        """
        cr.execute(sql, params)
        # 3️⃣ Recalcular dominios dinámicos basados en visibles
        cr.execute("""
            SELECT 
                ARRAY_AGG(DISTINCT product_tmpl_id),
                ARRAY_AGG(DISTINCT product_category)
            FROM sale_alternative_product_assistant_line
            WHERE wiz_id = %s AND visible = TRUE
        """, [wiz_id])

        template_ids, categ_ids = cr.fetchone()

        self.prod_template_domain = json.dumps([
            ('id', 'in', template_ids or [])
        ])

        self.categ_domain = json.dumps([
            ('id', 'in', categ_ids or [])
        ])
        # -----------------------
        # 4️⃣ Recalcular dominio de ATRIBUTOS basado en visibles
        # -----------------------
        cr.execute("""
            SELECT ARRAY_AGG(sub.id)
            FROM (
                SELECT MIN(ptav.id) AS id
                FROM sale_alternative_product_assistant_line l
                JOIN product_product p ON p.id = l.product_id
                JOIN product_variant_combination pvc 
                    ON pvc.product_product_id = p.id
                JOIN product_template_attribute_value ptav 
                    ON ptav.id = pvc.product_template_attribute_value_id
                JOIN product_attribute_value pav
                    ON pav.id = ptav.product_attribute_value_id
                WHERE l.wiz_id = %s
                  AND l.visible = TRUE
                GROUP BY pav.name
            ) sub
        """, [wiz_id])

        (attr_ids,) = cr.fetchone()

        self.attribute_alt_value_domain = json.dumps([
            ('id', 'in', attr_ids or [])
        ])
        return self.reload_wiz()

    def reload_wiz(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.alternative.product.assistant',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }    
    
    
class SaleAlternativeProductAssistantLine(models.TransientModel):
    _name = "sale.alternative.product.assistant.line"

    wiz_id = fields.Many2one('sale.alternative.product.assistant')
    visible = fields.Boolean(default=True, index=True)

    def get_sale_line_vals(self):
        return {
            'product_id': self.product_id.id,
            'name': self.product_id.name,
            'price_unit': self.product_id.list_price,
            'discount': self.wiz_id.sale_line_id.discount,
        }
    
    def add_product(self):
        vals = {'order_id': self.wiz_id.sale_line_id.order_id.id,
                'sequence': self.wiz_id.sale_line_id.sequence}
        vals.update(self.get_sale_line_vals())
        self.env['sale.order.line'].create(vals)
        return self.wiz_id.reload_wiz()

    def replace_product(self): 
        self.wiz_id.sale_line_id.write(self.get_sale_line_vals())
        return False
        

    
    location_id = fields.Many2one('stock.location', string="De")
    product_id = fields.Many2one('product.product', string="Producto")
    product_tmpl_id = fields.Many2one(related='product_id.product_tmpl_id', store=True, string="Plantilla Producto")
    product_template_variant_value_ids = fields.Many2many(related='product_id.product_template_variant_value_ids', store=False, string="Atributos")
    product_uom = fields.Many2one(related="product_id.uom_id", store=True, string="UdM")
    product_category = fields.Many2one(related="product_id.categ_id", store=True)
    list_price = fields.Float(related="product_id.lst_price", store=True)
    qty = fields.Float(string="Cantidad")
    location_available = fields.Float(string="Disponible")
    qty_available_not_res = fields.Float(string="No Reservado")
    location_virtual_available = fields.Float(string="Pronosticado")



