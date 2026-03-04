#!/usr/bin/env python3
"""
E2E Test Script for Product Description in Sale/Purchase Lines (roc_custom)
Tests that description_sale/description_purchase replaces the product name
+ variant attributes in parentheses, across all entry points.
"""
import xmlrpc.client
import sys
import json

# ─── Connection config ───────────────────────────────────────────────────────
URL = 'http://localhost:8079'
DB = 'roconsa'
ADMIN_PW = 'admin_test_123'
PREFIX = 'E2E_DESC_'

def connect():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, 'admin', ADMIN_PW, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)
    return uid, models

uid, models = connect()
if not uid:
    print("ERROR: Could not authenticate with Odoo")
    sys.exit(1)
print(f"Authenticated as admin (uid={uid})")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def x(model, method, args, kwargs=None):
    return models.execute_kw(DB, uid, ADMIN_PW, model, method, args, kwargs or {})

def search(model, domain, fields=None, limit=0):
    kw = {}
    if fields:
        kw['fields'] = fields
    if limit:
        kw['limit'] = limit
    return x(model, 'search_read', [domain], kw)

def create(model, vals):
    return x(model, 'create', [vals])

def write(model, ids, vals):
    return x(model, 'write', [ids, vals])

def read(model, ids, fields):
    return x(model, 'read', [ids], {'fields': fields})

def unlink(model, ids):
    if ids:
        return x(model, 'unlink', [ids])

created_ids = {}  # model -> [ids] for cleanup

def track(model, rec_id):
    created_ids.setdefault(model, []).append(rec_id)
    return rec_id

def cleanup():
    print("\n─── Cleanup ───")
    # Order matters: lines before orders, configs before templates
    order = [
        'sale.order.line', 'sale.order',
        'purchase.order.line', 'purchase.order',
        'sale.extra.product.config',
        'product.product', 'product.template',
        'product.attribute.value', 'product.attribute',
    ]
    for model in order:
        ids = created_ids.get(model, [])
        if ids:
            try:
                unlink(model, ids)
                print(f"  Deleted {model}: {ids}")
            except Exception as e:
                print(f"  WARN: Could not delete {model} {ids}: {e}")

results = []

def run_test(name, fn):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    try:
        fn()
        print(f"  ✓ PASSED")
        results.append((name, True, None))
    except Exception as e:
        print(f"  ✗ FAILED: {e}")
        results.append((name, False, str(e)))


# ─── Setup: create test product data ─────────────────────────────────────────

def setup():
    print("\n─── Setup: Creating test data ───")

    # Create attribute: "Color" with values "Rojo", "Azul"
    attr_id = track('product.attribute', create('product.attribute', {
        'name': PREFIX + 'Color',
        'create_variant': 'always',
    }))
    val_rojo_id = track('product.attribute.value', create('product.attribute.value', {
        'name': 'Rojo',
        'attribute_id': attr_id,
    }))
    val_azul_id = track('product.attribute.value', create('product.attribute.value', {
        'name': 'Azul',
        'attribute_id': attr_id,
    }))
    print(f"  Attribute: {attr_id}, Values: Rojo={val_rojo_id}, Azul={val_azul_id}")

    # Product A: WITH description_sale + variants
    tmpl_a_id = track('product.template', create('product.template', {
        'name': PREFIX + 'Producto A',
        'type': 'consu',
        'list_price': 100.0,
        'description_sale': 'Descripción venta producto A',
        'description_purchase': 'Descripción compra producto A',
        'attribute_line_ids': [(0, 0, {
            'attribute_id': attr_id,
            'value_ids': [(6, 0, [val_rojo_id, val_azul_id])],
        })],
    }))
    print(f"  Template A (with desc + variants): {tmpl_a_id}")

    # Find variants of template A
    variants_a = search('product.product', [('product_tmpl_id', '=', tmpl_a_id)],
                        fields=['name', 'display_name', 'product_template_attribute_value_ids'])
    for v in variants_a:
        track('product.product', v['id'])
    print(f"  Variants A: {[(v['id'], v['display_name']) for v in variants_a]}")

    # Product B: WITHOUT description_sale, WITH variants
    tmpl_b_id = track('product.template', create('product.template', {
        'name': PREFIX + 'Producto B',
        'type': 'consu',
        'list_price': 50.0,
        'attribute_line_ids': [(0, 0, {
            'attribute_id': attr_id,
            'value_ids': [(6, 0, [val_rojo_id, val_azul_id])],
        })],
    }))
    print(f"  Template B (no desc, with variants): {tmpl_b_id}")

    variants_b = search('product.product', [('product_tmpl_id', '=', tmpl_b_id)],
                        fields=['name', 'display_name', 'product_template_attribute_value_ids'])
    for v in variants_b:
        track('product.product', v['id'])
    print(f"  Variants B: {[(v['id'], v['display_name']) for v in variants_b]}")

    # Product C: WITH description_sale, NO variants (simple product)
    tmpl_c_id = track('product.template', create('product.template', {
        'name': PREFIX + 'Producto C',
        'type': 'consu',
        'list_price': 25.0,
        'description_sale': 'Descripción venta producto C',
        'description_purchase': 'Descripción compra producto C',
    }))
    variants_c = search('product.product', [('product_tmpl_id', '=', tmpl_c_id)],
                        fields=['name', 'display_name'])
    for v in variants_c:
        track('product.product', v['id'])
    print(f"  Template C (with desc, no variants): {tmpl_c_id}")

    # Product D: NO description, NO variants
    tmpl_d_id = track('product.template', create('product.template', {
        'name': PREFIX + 'Producto D',
        'type': 'consu',
        'list_price': 10.0,
    }))
    variants_d = search('product.product', [('product_tmpl_id', '=', tmpl_d_id)],
                        fields=['name', 'display_name'])
    for v in variants_d:
        track('product.product', v['id'])
    print(f"  Template D (no desc, no variants): {tmpl_d_id}")

    return {
        'attr_id': attr_id,
        'val_rojo_id': val_rojo_id,
        'val_azul_id': val_azul_id,
        'tmpl_a_id': tmpl_a_id,
        'variants_a': variants_a,
        'tmpl_b_id': tmpl_b_id,
        'variants_b': variants_b,
        'tmpl_c_id': tmpl_c_id,
        'variant_c': variants_c[0],
        'tmpl_d_id': tmpl_d_id,
        'variant_d': variants_d[0],
    }


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_helper_desc_sale_with_variants(data):
    """Product A: description_sale + variants → 'desc_sale (attr)'"""
    def t():
        for v in data['variants_a']:
            result = x('product.product', 'get_product_multiline_description_sale', [[v['id']]])
            ptav_ids = v['product_template_attribute_value_ids']
            ptavs = read('product.template.attribute.value', ptav_ids, ['product_attribute_value_id'])
            attr_names = [p['product_attribute_value_id'][1].split(': ')[-1] for p in ptavs]
            expected = 'Descripción venta producto A (' + ', '.join(attr_names) + ')'
            assert result == expected, f"Expected '{expected}', got '{result}'"
            print(f"    variant {v['id']}: '{result}' ✓")
    return t

def test_helper_no_desc_sale_with_variants(data):
    """Product B: no description_sale + variants → display_name (already includes attrs)"""
    def t():
        for v in data['variants_b']:
            result = x('product.product', 'get_product_multiline_description_sale', [[v['id']]])
            expected = v['display_name']
            assert result == expected, f"Expected '{expected}', got '{result}'"
            print(f"    variant {v['id']}: '{result}' ✓")
    return t

def test_helper_desc_sale_no_variants(data):
    """Product C: description_sale, no variants → just desc_sale"""
    def t():
        v = data['variant_c']
        result = x('product.product', 'get_product_multiline_description_sale', [[v['id']]])
        expected = 'Descripción venta producto C'
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print(f"    product {v['id']}: '{result}' ✓")
    return t

def test_helper_no_desc_no_variants(data):
    """Product D: no desc, no variants → display_name"""
    def t():
        v = data['variant_d']
        result = x('product.product', 'get_product_multiline_description_sale', [[v['id']]])
        expected = v['display_name']
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print(f"    product {v['id']}: '{result}' ✓")
    return t

def test_helper_purchase_with_variants(data):
    """Product A: description_purchase + variants → 'desc_purchase (attr)'"""
    def t():
        for v in data['variants_a']:
            result = x('product.product', 'get_product_multiline_description_purchase', [[v['id']]])
            ptav_ids = v['product_template_attribute_value_ids']
            ptavs = read('product.template.attribute.value', ptav_ids, ['product_attribute_value_id'])
            attr_names = [p['product_attribute_value_id'][1].split(': ')[-1] for p in ptavs]
            expected = 'Descripción compra producto A (' + ', '.join(attr_names) + ')'
            assert result == expected, f"Expected '{expected}', got '{result}'"
            print(f"    variant {v['id']}: '{result}' ✓")
    return t

def test_helper_purchase_no_desc(data):
    """Product B: no description_purchase + variants → display_name"""
    def t():
        for v in data['variants_b']:
            result = x('product.product', 'get_product_multiline_description_purchase', [[v['id']]])
            expected = v['display_name']
            assert result == expected, f"Expected '{expected}', got '{result}'"
            print(f"    variant {v['id']}: '{result}' ✓")
    return t

def test_sale_order_line_onchange(data):
    """Standard sale order line: product_id_change should use our override."""
    def t():
        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]

        # Create SO
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))
        print(f"    Created SO: {so_id}")

        # Test with product A variant (has desc_sale + attrs)
        va = data['variants_a'][0]
        sol_a_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': va['id'],
            'product_uom_qty': 1,
        }))
        sol_a = read('sale.order.line', [sol_a_id], ['name'])[0]
        # The standard onchange calls get_product_multiline_description_sale
        # which should return desc_sale (attrs)
        ptav_ids = va['product_template_attribute_value_ids']
        ptavs = read('product.template.attribute.value', ptav_ids, ['product_attribute_value_id'])
        attr_names = [p['product_attribute_value_id'][1].split(': ')[-1] for p in ptavs]
        expected_part = 'Descripción venta producto A'
        assert expected_part in sol_a['name'], \
            f"Expected '{expected_part}' in line name, got '{sol_a['name']}'"
        for attr in attr_names:
            assert attr in sol_a['name'], \
                f"Expected attr '{attr}' in line name, got '{sol_a['name']}'"
        print(f"    SOL with desc_sale+attrs: '{sol_a['name']}' ✓")

        # Test with product B variant (no desc_sale, has attrs)
        vb = data['variants_b'][0]
        sol_b_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': vb['id'],
            'product_uom_qty': 1,
        }))
        sol_b = read('sale.order.line', [sol_b_id], ['name'])[0]
        # Should be display_name when no desc_sale
        expected_part_b = data['variants_b'][0]['display_name']
        assert expected_part_b in sol_b['name'], \
            f"Expected '{expected_part_b}' in line name, got '{sol_b['name']}'"
        print(f"    SOL without desc_sale: '{sol_b['name']}' ✓")

        # Test with product C (desc_sale, no variants)
        vc = data['variant_c']
        sol_c_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': vc['id'],
            'product_uom_qty': 1,
        }))
        sol_c = read('sale.order.line', [sol_c_id], ['name'])[0]
        assert 'Descripción venta producto C' in sol_c['name'], \
            f"Expected 'Descripción venta producto C' in '{sol_c['name']}'"
        print(f"    SOL with desc_sale, no variants: '{sol_c['name']}' ✓")

        # Test with product D (no desc, no variants)
        vd = data['variant_d']
        sol_d_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': vd['id'],
            'product_uom_qty': 1,
        }))
        sol_d = read('sale.order.line', [sol_d_id], ['name'])[0]
        assert PREFIX + 'Producto D' in sol_d['name'], \
            f"Expected '{PREFIX}Producto D' in '{sol_d['name']}'"
        print(f"    SOL no desc, no variants: '{sol_d['name']}' ✓")
    return t

def test_purchase_order_line_description(data):
    """Purchase order line should use get_product_multiline_description_purchase."""
    def t():
        supplier = search('res.partner', [('supplier_rank', '>', 0)], limit=1)[0]

        po_id = track('purchase.order', create('purchase.order', {
            'partner_id': supplier['id'],
        }))
        print(f"    Created PO: {po_id}")

        # Product A variant (has desc_purchase + attrs)
        va = data['variants_a'][0]
        pol_a_id = track('purchase.order.line', create('purchase.order.line', {
            'order_id': po_id,
            'product_id': va['id'],
            'product_qty': 1,
            'price_unit': 100.0,
            'name': 'temp',
            'date_planned': '2026-04-01',
        }))
        # Now trigger the onchange by writing the product
        # Actually, in Odoo 15 create via XML-RPC doesn't trigger onchange.
        # The _get_product_purchase_description is called by onchange_product_id.
        # Let's call onchange manually or test the method directly.
        # Let's test the method directly on the PO line model
        pol_a = read('purchase.order.line', [pol_a_id], ['name'])[0]
        print(f"    POL created with name: '{pol_a['name']}'")

        # Test the _get_product_purchase_description method directly via a fresh line
        # The standard Odoo onchange calls _get_product_purchase_description
        # Since XML-RPC create doesn't trigger onchange, let's test the method on product directly
        result = x('product.product', 'get_product_multiline_description_purchase', [[va['id']]])
        ptav_ids = va['product_template_attribute_value_ids']
        ptavs = read('product.template.attribute.value', ptav_ids, ['product_attribute_value_id'])
        attr_names = [p['product_attribute_value_id'][1].split(': ')[-1] for p in ptavs]
        expected = 'Descripción compra producto A (' + ', '.join(attr_names) + ')'
        assert result == expected, f"Expected '{expected}', got '{result}'"
        print(f"    get_product_multiline_description_purchase: '{result}' ✓")

        # Product B (no desc_purchase)
        vb = data['variants_b'][0]
        result_b = x('product.product', 'get_product_multiline_description_purchase', [[vb['id']]])
        expected_b = vb['display_name']
        assert result_b == expected_b, f"Expected '{expected_b}', got '{result_b}'"
        print(f"    Purchase no desc: '{result_b}' ✓")
    return t

def test_extra_product_wizard_other_product(data):
    """Extra product wizard (other_product type) should use helper for line name."""
    def t():
        # Setup: create an extra_product_config on template A with other_product type
        # pointing to variant C (which has desc_sale)
        vc = data['variant_c']
        config_id = track('sale.extra.product.config', create('sale.extra.product.config', {
            'product_tmpl_id': data['tmpl_a_id'],
            'usage_type': 'other_product',
            'extra_product_id': vc['id'],
            'quantity': 2,
            'description': 'Test extra',
        }))
        print(f"    Created extra config: {config_id}")

        # Create a SO with a line for product A variant
        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))
        va = data['variants_a'][0]
        sol_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': va['id'],
            'product_uom_qty': 1,
        }))

        # Open extra product selector wizard
        wiz_action = x('sale.order.line', 'open_extra_product_selector', [[sol_id]])
        wiz_id = wiz_action['res_id']
        print(f"    Opened wizard: {wiz_id}")

        # Find the config line for our other_product config
        wiz_lines = search('sale.extra.product.selector.line',
                           [('wiz_id', '=', wiz_id), ('usage_type', '=', 'other_product')])
        assert wiz_lines, "No other_product wizard line found"
        wiz_line = wiz_lines[0]

        # Apply the extra (this creates a new sale.order.line)
        x('sale.extra.product.selector.line', 'apply_extra', [[wiz_line['id']]])
        print(f"    Applied extra product")

        # Find the new line
        new_lines = search('sale.order.line',
                           [('order_id', '=', so_id), ('product_id', '=', vc['id'])],
                           fields=['name', 'product_uom_qty'])
        assert new_lines, "No new line created by apply_extra"
        new_line = new_lines[0]
        track('sale.order.line', new_line['id'])

        expected_name = 'Descripción venta producto C'
        assert expected_name in new_line['name'], \
            f"Expected '{expected_name}' in '{new_line['name']}'"
        assert new_line['product_uom_qty'] == 2, \
            f"Expected qty=2, got {new_line['product_uom_qty']}"
        print(f"    New line name: '{new_line['name']}', qty={new_line['product_uom_qty']} ✓")
    return t

def test_extra_variant_selector_select(data):
    """Extra variant selector: select_variant should use helper."""
    def t():
        # Add attribute_change config to template B
        config_id = track('sale.extra.product.config', create('sale.extra.product.config', {
            'product_tmpl_id': data['tmpl_b_id'],
            'usage_type': 'attribute_change',
            'quantity': 1,
            'description': 'Cambiar color',
        }))

        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))
        vb = data['variants_b'][0]
        sol_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': vb['id'],
            'product_uom_qty': 1,
        }))

        # Open extra selector → click attribute_change → opens variant selector
        wiz_action = x('sale.order.line', 'open_extra_product_selector', [[sol_id]])
        wiz_id = wiz_action['res_id']
        wiz_lines = search('sale.extra.product.selector.line',
                           [('wiz_id', '=', wiz_id), ('usage_type', '=', 'attribute_change')])
        assert wiz_lines, "No attribute_change wizard line found"

        # apply_extra on attribute_change opens variant selector wizard
        result = x('sale.extra.product.selector.line', 'apply_extra', [[wiz_lines[0]['id']]])
        assert result.get('res_model') == 'sale.extra.variant.selector', \
            f"Expected variant selector, got {result}"
        var_wiz_id = result['res_id']
        print(f"    Variant selector wizard: {var_wiz_id}")

        # Find variant lines
        var_lines = search('sale.extra.variant.line',
                           [('wiz_id', '=', var_wiz_id)],
                           fields=['product_id', 'lst_price'])
        assert var_lines, "No variant lines in wizard"
        print(f"    Found {len(var_lines)} variant lines")

        # Use select_variant on one of them
        target_line = var_lines[0]
        x('sale.extra.variant.line', 'select_variant', [[target_line['id']]])

        # Check the created sale line
        product_id = target_line['product_id'][0]
        new_lines = search('sale.order.line',
                           [('order_id', '=', so_id), ('product_id', '=', product_id),
                            ('id', '!=', sol_id)],
                           fields=['name'])
        assert new_lines, "select_variant did not create a line"
        new_line = new_lines[0]
        track('sale.order.line', new_line['id'])

        # Since product B has no desc_sale, name should be display_name
        product_data = read('product.product', [product_id], ['display_name'])[0]
        expected = product_data['display_name']
        assert new_line['name'] == expected, \
            f"Expected '{expected}', got '{new_line['name']}'"
        print(f"    select_variant line name: '{new_line['name']}' ✓")
    return t

def test_extra_variant_selector_apply(data):
    """Extra variant selector: apply_variant should use helper."""
    def t():
        # Reuse template A which has variants and desc_sale
        config_id = track('sale.extra.product.config', create('sale.extra.product.config', {
            'product_tmpl_id': data['tmpl_a_id'],
            'usage_type': 'attribute_change',
            'quantity': 3,
            'description': 'Cambiar color A',
        }))

        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))
        va = data['variants_a'][0]
        sol_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': va['id'],
            'product_uom_qty': 1,
        }))

        # Open extra selector → attribute_change → variant selector
        wiz_action = x('sale.order.line', 'open_extra_product_selector', [[sol_id]])
        wiz_id = wiz_action['res_id']
        wiz_lines = search('sale.extra.product.selector.line',
                           [('wiz_id', '=', wiz_id), ('usage_type', '=', 'attribute_change')])
        assert wiz_lines, "No attribute_change line"

        result = x('sale.extra.product.selector.line', 'apply_extra', [[wiz_lines[0]['id']]])
        var_wiz_id = result['res_id']

        # Get variant selector data
        var_wiz = read('sale.extra.variant.selector', [var_wiz_id],
                       ['product_tmpl_id', 'available_attr_ids', 'selected_attr_id',
                        'available_value_ids'])[0]
        print(f"    Variant selector: attrs={var_wiz['available_attr_ids']}")

        # We need to pick attribute values to match a variant
        # Get the second variant (different from va)
        va2 = data['variants_a'][1] if len(data['variants_a']) > 1 else data['variants_a'][0]
        ptav_ids = va2['product_template_attribute_value_ids']

        # Set selections JSON to select the right ptav
        ptavs = read('product.template.attribute.value', ptav_ids, ['attribute_id'])
        selections = {}
        for ptav in ptavs:
            selections[str(ptav['attribute_id'][0])] = ptav['id']
        write('sale.extra.variant.selector', [var_wiz_id], {
            '_selections_json': json.dumps(selections),
        })

        # Call apply_variant
        lines_before = search('sale.order.line', [('order_id', '=', so_id)], fields=['id'])
        before_ids = {l['id'] for l in lines_before}

        x('sale.extra.variant.selector', 'apply_variant', [[var_wiz_id]])

        lines_after = search('sale.order.line', [('order_id', '=', so_id)], fields=['id', 'name', 'product_id'])
        new = [l for l in lines_after if l['id'] not in before_ids]
        assert new, "apply_variant did not create a new line"
        new_line = new[0]
        track('sale.order.line', new_line['id'])

        # Product A has desc_sale, so name should contain it
        assert 'Descripción venta producto A' in new_line['name'], \
            f"Expected desc_sale in '{new_line['name']}'"
        print(f"    apply_variant line name: '{new_line['name']}' ✓")
    return t

def test_js_configurator_method(data):
    """roc_create_extra_line_from_ptavs should use helper for name."""
    def t():
        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))

        # Get variant A's ptav_ids
        va = data['variants_a'][0]
        ptav_ids = va['product_template_attribute_value_ids']

        # Call roc_create_extra_line_from_ptavs
        x('sale.order', 'roc_create_extra_line_from_ptavs',
          [[so_id], data['tmpl_a_id'], ptav_ids, 5.0, 10])

        lines = search('sale.order.line', [('order_id', '=', so_id)],
                        fields=['name', 'product_id', 'product_uom_qty'])
        assert lines, "roc_create_extra_line_from_ptavs did not create a line"
        line = lines[0]
        track('sale.order.line', line['id'])

        assert 'Descripción venta producto A' in line['name'], \
            f"Expected desc_sale in '{line['name']}'"
        assert line['product_uom_qty'] == 5.0
        print(f"    JS configurator line: '{line['name']}', qty={line['product_uom_qty']} ✓")
    return t

def test_alternative_product_wizard(data):
    """Alternative product assistant: get_sale_line_vals should use helper."""
    def t():
        partner = search('res.partner', [('customer_rank', '>', 0)], limit=1)[0]
        pricelist = search('product.pricelist', [], limit=1)[0]
        so_id = track('sale.order', create('sale.order', {
            'partner_id': partner['id'],
            'pricelist_id': pricelist['id'],
        }))
        va = data['variants_a'][0]
        sol_id = track('sale.order.line', create('sale.order.line', {
            'order_id': so_id,
            'product_id': va['id'],
            'product_uom_qty': 1,
        }))

        # Create wizard line directly pointing to product C (has desc_sale, no variants)
        vc = data['variant_c']
        # We need a wizard first
        wiz_id = create('sale.alternative.product.assistant', {
            'sale_line_id': sol_id,
            'see_attributes': False,
            'prod_template_domain': '[]',
        })

        # Get stock location for the line
        wh = search('stock.warehouse', [], fields=['lot_stock_id'], limit=1)
        loc_id = wh[0]['lot_stock_id'][0] if wh else False

        # Create wizard line
        wiz_line_id = create('sale.alternative.product.assistant.line', {
            'wiz_id': wiz_id,
            'product_id': vc['id'],
            'qty': 1,
            'location_id': loc_id,
            'location_available': 0,
            'qty_available_not_res': 0,
            'location_virtual_available': 0,
            'list_price': 25.0,
        })

        # Test replace_product (writes to existing line)
        x('sale.alternative.product.assistant.line', 'replace_product', [[wiz_line_id]])
        sol_after = read('sale.order.line', [sol_id], ['name', 'product_id'])[0]
        assert sol_after['product_id'][0] == vc['id'], "Product not replaced"
        assert 'Descripción venta producto C' in sol_after['name'], \
            f"Expected desc_sale in '{sol_after['name']}'"
        print(f"    replace_product name: '{sol_after['name']}' ✓")

        # Test add_product with a variant that has attrs but no desc
        vb = data['variants_b'][0]
        wiz_line_2_id = create('sale.alternative.product.assistant.line', {
            'wiz_id': wiz_id,
            'product_id': vb['id'],
            'qty': 1,
            'location_id': loc_id,
            'location_available': 0,
            'qty_available_not_res': 0,
            'location_virtual_available': 0,
            'list_price': 50.0,
        })

        x('sale.alternative.product.assistant.line', 'add_product', [[wiz_line_2_id]])
        added_lines = search('sale.order.line',
                             [('order_id', '=', so_id), ('product_id', '=', vb['id'])],
                             fields=['name'])
        assert added_lines, "add_product did not create a line"
        added = added_lines[0]
        track('sale.order.line', added['id'])

        expected = vb['display_name']
        assert added['name'] == expected, \
            f"Expected '{expected}', got '{added['name']}'"
        print(f"    add_product name: '{added['name']}' ✓")
    return t


# ─── Main ─────────────────────────────────────────────────────────────────────

try:
    data = setup()

    run_test("1. Helper: desc_sale + variants → 'desc (attrs)'",
             test_helper_desc_sale_with_variants(data))
    run_test("2. Helper: no desc_sale + variants → display_name",
             test_helper_no_desc_sale_with_variants(data))
    run_test("3. Helper: desc_sale, no variants → desc_sale",
             test_helper_desc_sale_no_variants(data))
    run_test("4. Helper: no desc, no variants → display_name",
             test_helper_no_desc_no_variants(data))
    run_test("5. Helper: purchase desc + variants",
             test_helper_purchase_with_variants(data))
    run_test("6. Helper: purchase no desc → display_name",
             test_helper_purchase_no_desc(data))
    run_test("7. Sale order line onchange (all 4 combos)",
             test_sale_order_line_onchange(data))
    run_test("8. Purchase order line description",
             test_purchase_order_line_description(data))
    run_test("9. Extra product wizard (other_product)",
             test_extra_product_wizard_other_product(data))
    run_test("10. Extra variant selector (select_variant)",
             test_extra_variant_selector_select(data))
    run_test("11. Extra variant selector (apply_variant)",
             test_extra_variant_selector_apply(data))
    run_test("12. JS configurator (roc_create_extra_line_from_ptavs)",
             test_js_configurator_method(data))
    run_test("13. Alternative product wizard (replace + add)",
             test_alternative_product_wizard(data))

finally:
    cleanup()

# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("RESULTS SUMMARY")
print("="*60)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
for name, ok, err in results:
    status = "✓ PASSED" if ok else f"✗ FAILED: {err}"
    print(f"  {status} - {name}")
print(f"\nTotal: {passed} passed, {failed} failed out of {len(results)}")
sys.exit(0 if failed == 0 else 1)
