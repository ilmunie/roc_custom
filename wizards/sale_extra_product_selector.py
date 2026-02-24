import json
from odoo import fields, models, api


class SaleExtraProductSelector(models.TransientModel):
    _name = 'sale.extra.product.selector'

    sale_line_id = fields.Many2one('sale.order.line', required=True)
    product_name = fields.Char(related='sale_line_id.product_id.name', string="Producto")
    config_line_ids = fields.One2many('sale.extra.product.selector.line', 'wiz_id', string="Extras disponibles")

    @api.model
    def create(self, vals):
        if vals.get('sale_line_id'):
            sale_line = self.env['sale.order.line'].browse(vals['sale_line_id'])
            configs = sale_line.product_id.product_tmpl_id.extra_product_config_ids.filtered(
                lambda x: x.usage_type in ('attribute_change', 'other_product')
            )
            if configs:
                vals['config_line_ids'] = [(0, 0, {'config_id': c.id}) for c in configs]
        return super().create(vals)


class SaleExtraProductSelectorLine(models.TransientModel):
    _name = 'sale.extra.product.selector.line'
    _order = 'sequence'

    wiz_id = fields.Many2one('sale.extra.product.selector', ondelete='cascade')
    config_id = fields.Many2one('sale.extra.product.config', required=True)
    sequence = fields.Integer(related='config_id.sequence', store=True)
    description = fields.Text(related='config_id.description', string="Descripción")
    usage_type = fields.Selection(related='config_id.usage_type', string="Tipo de Uso")
    quantity = fields.Float(related='config_id.quantity', string="Cantidad")
    extra_product_id = fields.Many2one(related='config_id.extra_product_id', string="Producto Extra")

    def apply_extra(self):
        self.ensure_one()
        config = self.config_id
        sale_line = self.wiz_id.sale_line_id

        if config.usage_type == 'other_product' and config.extra_product_id:
            self.env['sale.order.line'].create({
                'order_id': sale_line.order_id.id,
                'product_id': config.extra_product_id.id,
                'name': config.extra_product_id.display_name,
                'product_uom_qty': config.quantity,
                'product_uom': config.extra_product_id.uom_id.id,
                'price_unit': config.extra_product_id.lst_price,
                'sequence': sale_line.sequence + 1,
            })
            return {'type': 'ir.actions.act_window_close'}

        elif config.usage_type == 'attribute_change':
            product_tmpl = sale_line.product_id.product_tmpl_id
            wiz = self.env['sale.extra.variant.selector'].create({
                'sale_line_id': sale_line.id,
                'product_tmpl_id': product_tmpl.id,
                'product_uom_qty': config.quantity,
            })
            return wiz._reopen()

        return {'type': 'ir.actions.act_window_close'}


# ── kept for backwards compat (unused by the new variant selector) ──
class SaleExtraAttrLine(models.TransientModel):
    """One row per attribute of the product template."""
    _name = 'sale.extra.attr.line'

    wiz_id = fields.Many2one('sale.extra.variant.selector', ondelete='cascade')
    attribute_id = fields.Many2one('product.attribute', string="Atributo", readonly=True)
    available_ptav_ids = fields.Many2many(
        'product.template.attribute.value',
        'sale_extra_attr_line_avail_ptav_rel',
        string="Valores disponibles",
        readonly=True,
    )
    selected_ptav_id = fields.Many2one(
        'product.template.attribute.value',
        string="Valor",
        domain="[('id', 'in', available_ptav_ids)]",
    )


# ── Variant line (one row per matching variant) ──
class SaleExtraVariantLine(models.TransientModel):
    _name = 'sale.extra.variant.line'
    _description = 'Variant line inside variant selector wizard'

    wiz_id = fields.Many2one('sale.extra.variant.selector', ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Variante", readonly=True)
    ptav_ids = fields.Many2many(
        'product.template.attribute.value',
        'sale_extra_variant_line_ptav_rel',
        string="Atributos",
        readonly=True,
    )
    lst_price = fields.Float(string="Precio", readonly=True)

    def select_variant(self):
        """Create a sale order line for this variant and close the wizard."""
        self.ensure_one()
        wiz = self.wiz_id
        sale_line = wiz.sale_line_id
        product = self.product_id
        self.env['sale.order.line'].create({
            'order_id': sale_line.order_id.id,
            'product_id': product.id,
            'name': product.display_name,
            'product_uom_qty': wiz.product_uom_qty,
            'product_uom': product.uom_id.id,
            'price_unit': product.lst_price,
            'sequence': sale_line.sequence + 1,
        })
        return {'type': 'ir.actions.act_window_close'}


# ── Redesigned variant selector with radio-button UX ──
class SaleExtraVariantSelector(models.TransientModel):
    """Wizard to select a product variant by choosing attribute values."""
    _name = 'sale.extra.variant.selector'
    _description = 'Seleccionar Variante'

    sale_line_id = fields.Many2one('sale.order.line', required=True)
    product_tmpl_id = fields.Many2one(
        'product.template', required=True,
        string="Plantilla Producto", readonly=True,
    )
    product_uom_qty = fields.Float(string="Cantidad", default=1)

    # -- kept for DB compat, no longer used in the view --
    attr_line_ids = fields.One2many('sale.extra.attr.line', 'wiz_id', string="Atributos")

    # -- radio-based attribute selector --
    selected_attr_id = fields.Many2one('product.attribute', string="Atributo")
    available_attr_ids = fields.Many2many(
        'product.attribute',
        'sale_extra_variant_sel_avail_attr_rel',
        string="Atributos disponibles",
    )

    # -- radio-based value selector --
    selected_value_id = fields.Many2one(
        'product.template.attribute.value', string="Valor",
    )
    available_value_ids = fields.Many2many(
        'product.template.attribute.value',
        'sale_extra_variant_sel_avail_val_rel',
        string="Valores disponibles",
    )

    # -- summary of current selections --
    config_summary = fields.Char(compute='_compute_config_summary', string="Configuración")

    # -- dict stored as JSON: {attr_id: ptav_id, ...} --
    _selections_json = fields.Text(default='{}')

    # -- variant list (persisted rows with select button) --
    variant_line_ids = fields.One2many(
        'sale.extra.variant.line', 'wiz_id', string="Variantes",
    )

    # ── helpers ──────────────────────────────────────────────────────

    def _get_selections(self):
        """Return the current selections dict {attr_id(int): ptav_id(int)}."""
        try:
            raw = json.loads(self._selections_json or '{}')
            return {int(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError):
            return {}

    def _set_selections(self, selections):
        self._selections_json = json.dumps({str(k): v for k, v in selections.items()})

    def _get_template_attrs(self):
        """Return product.template.attribute.line recordset for the template."""
        return self.product_tmpl_id.attribute_line_ids

    def _reopen(self):
        """Return action to reopen this wizard."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Seleccionar Variante',
            'res_model': 'sale.extra.variant.selector',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref('roc_custom.view_sale_extra_variant_selector_form').id, 'form')],
            'target': 'new',
        }

    # ── config summary ───────────────────────────────────────────────

    @api.depends('_selections_json')
    def _compute_config_summary(self):
        for wiz in self:
            selections = wiz._get_selections()
            if not selections:
                wiz.config_summary = ''
                continue
            ptav_ids = list(selections.values())
            ptavs = self.env['product.template.attribute.value'].browse(ptav_ids).exists()
            parts = []
            for ptav in ptavs:
                parts.append('%s: %s' % (ptav.attribute_id.name, ptav.name))
            wiz.config_summary = ' | '.join(parts)

    # ── create override ──────────────────────────────────────────────

    @api.model
    def create(self, vals):
        wiz = super().create(vals)
        if wiz.product_tmpl_id:
            attr_lines = wiz._get_template_attrs()
            wiz.available_attr_ids = [(6, 0, attr_lines.mapped('attribute_id').ids)]
            first_attr_line = attr_lines[:1]
            if first_attr_line:
                wiz.selected_attr_id = first_attr_line.attribute_id.id
                wiz.available_value_ids = [(6, 0, first_attr_line.product_template_value_ids.ids)]
            # Persist all variants in DB
            all_variants = self.env['product.product'].search([
                ('product_tmpl_id', '=', wiz.product_tmpl_id.id),
            ])
            for variant in all_variants:
                self.env['sale.extra.variant.line'].create({
                    'wiz_id': wiz.id,
                    'product_id': variant.id,
                    'ptav_ids': [(6, 0, variant.product_template_attribute_value_ids.ids)],
                    'lst_price': variant.lst_price,
                })
        return wiz

    # ── onchange: attribute selected ─────────────────────────────────

    @api.onchange('selected_attr_id')
    def _onchange_selected_attr_id(self):
        """When user clicks a different attribute radio, load its values and restore previous selection."""
        if not self.selected_attr_id:
            self.selected_value_id = False
            self.available_value_ids = [(5, 0, 0)]
            return
        attr_line = self._get_template_attrs().filtered(
            lambda l: l.attribute_id == self.selected_attr_id
        )
        if attr_line:
            self.available_value_ids = [(6, 0, attr_line.product_template_value_ids.ids)]
        else:
            self.available_value_ids = [(5, 0, 0)]
        selections = self._get_selections()
        prev_ptav_id = selections.get(self.selected_attr_id.id)
        if prev_ptav_id:
            self.selected_value_id = prev_ptav_id
        else:
            self.selected_value_id = False

    # ── onchange: value selected → update JSON + refresh variant list ──

    @api.onchange('selected_value_id')
    def _onchange_selected_value_id(self):
        """When user picks a value radio, save selection and refresh variant list."""
        if not self.selected_attr_id:
            return
        selections = self._get_selections()
        if self.selected_value_id:
            selections[self.selected_attr_id.id] = self.selected_value_id.id
        else:
            selections.pop(self.selected_attr_id.id, None)
        self._set_selections(selections)
        self._refresh_variant_lines(selections)

    # ── refresh variant list (onchange commands) ─────────────────────

    def _refresh_variant_lines(self, selections=None):
        """Rebuild variant_line_ids via onchange commands."""
        if selections is None:
            selections = self._get_selections()
        selected_ptav_ids = set(selections.values())

        all_variants = self.env['product.product'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
        ])

        if selected_ptav_ids:
            matching = all_variants.filtered(
                lambda p: selected_ptav_ids.issubset(
                    set(p.product_template_attribute_value_ids.ids)
                )
            )
        else:
            matching = all_variants

        cmds = [(5, 0, 0)]
        for variant in matching:
            cmds.append((0, 0, {
                'product_id': variant.id,
                'ptav_ids': [(6, 0, variant.product_template_attribute_value_ids.ids)],
                'lst_price': variant.lst_price,
            }))
        self.variant_line_ids = cmds

    # ── button: clear all selections ─────────────────────────────────

    def clear_selections(self):
        """Clear all attribute selections and reload all variants."""
        self.ensure_one()
        self._set_selections({})
        self.selected_value_id = False
        # Rebuild in DB since this is a button (not onchange)
        self.variant_line_ids.unlink()
        all_variants = self.env['product.product'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
        ])
        for variant in all_variants:
            self.env['sale.extra.variant.line'].create({
                'wiz_id': self.id,
                'product_id': variant.id,
                'ptav_ids': [(6, 0, variant.product_template_attribute_value_ids.ids)],
                'lst_price': variant.lst_price,
            })
        return self._reopen()

    # ── button: add by current config (exact match) ──────────────────

    def apply_variant(self):
        """Create a sale line for the variant that exactly matches current selections."""
        self.ensure_one()
        selections = self._get_selections()
        selected_ptav_ids = set(selections.values())
        if not selected_ptav_ids:
            return {'type': 'ir.actions.act_window_close'}

        candidates = self.env['product.product'].search([
            ('product_tmpl_id', '=', self.product_tmpl_id.id),
        ])

        product = candidates.filtered(
            lambda p: set(p.product_template_attribute_value_ids.ids) == selected_ptav_ids
        )[:1]
        if not product:
            product = candidates.filtered(
                lambda p: selected_ptav_ids.issubset(
                    set(p.product_template_attribute_value_ids.ids)
                )
            )[:1]

        if product:
            sale_line = self.sale_line_id
            self.env['sale.order.line'].create({
                'order_id': sale_line.order_id.id,
                'product_id': product.id,
                'name': product.display_name,
                'product_uom_qty': self.product_uom_qty,
                'product_uom': product.uom_id.id,
                'price_unit': product.lst_price,
                'sequence': sale_line.sequence + 1,
            })
        return {'type': 'ir.actions.act_window_close'}
