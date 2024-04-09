from odoo import fields, models, api


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _prepare_sellers(self, params=False):
        sellers = super(ProductProduct, self)._prepare_sellers(params=params)
        if len(sellers) > 1:
            sellers = sellers.filtered(lambda s: s.price > 0)
        return sellers
    def set_cost_from_pricelist(self):
        product_to_compute = self.env['product.product'].browse(self._context.get('active_ids', []))
        for prod in product_to_compute:
            cost = 0
            discount_amount = 0
            seller = prod._select_seller()
            if seller:
                if seller.variant_extra_ids:
                    final_price = seller.get_final_price(prod)
                    cost = final_price
                    discount_amount = seller.discount*final_price/100
                else:
                    cost = seller.price
                    discount_amount = seller.discount * cost / 100
            if not seller and prod.product_tmpl_id.is_combo:
                price_unit = 0
                discount_amount = 0
                for combo_line in prod.product_tmpl_id.combo_product_id:
                    seller = combo_line.product_id.with_company(prod.company_id)._select_seller()
                    if seller:
                        if seller.variant_extra_ids:
                            aux_var = seller.get_final_price(combo_line.product_id) * combo_line.product_quantity
                            discount_amount += seller.discount * aux_var / 100
                            price_unit += aux_var
                        else:
                            aux_var = seller.price * combo_line.product_quantity
                            discount_amount += seller.discount * aux_var / 100
                            price_unit += aux_var
                cost = price_unit
            prod.standard_price = cost - discount_amount
        return False

    def set_cost_from_last_purchase(self):
        return False