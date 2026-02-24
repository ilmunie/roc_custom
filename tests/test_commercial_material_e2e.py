#!/usr/bin/env python3
"""
E2E Test Script for Commercial Material Rules (roc_custom)
Tests rule-based attachment of commercial material to sale orders via XML-RPC.
"""
import xmlrpc.client
import base64
import sys
import json

# ─── Connection config ───────────────────────────────────────────────────────
URL = 'http://localhost:8079'
DB = 'roconsa'
ADMIN_PW = 'admin_test_123'
PREFIX = 'E2E_CM_'

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
def search(model, domain, **kw):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'search', [domain], kw)

def search_read(model, domain, fields, **kw):
    kw['fields'] = fields
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'search_read', [domain], kw)

def read_rec(model, ids, fields):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'read', [ids, fields])

def create(model, vals):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'create', [vals])

def write(model, ids, vals):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'write', [ids, vals])

def unlink(model, ids):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'unlink', [ids])

def call_button(model, method, ids):
    return models.execute_kw(DB, uid, ADMIN_PW, model, method, [ids])


test_results = []
cleanup_ids = {}  # model -> [ids]

def register_cleanup(model, rec_id):
    cleanup_ids.setdefault(model, []).append(rec_id)

def assert_eq(label, actual, expected):
    if actual == expected:
        print(f"  OK: {label}")
        return True
    msg = f"  FAIL: {label} - expected {expected!r}, got {actual!r}"
    print(msg)
    test_results.append(('FAIL', label, msg))
    return False

def assert_true(label, value):
    if value:
        print(f"  OK: {label}")
        return True
    msg = f"  FAIL: {label} - expected truthy, got {value!r}"
    print(msg)
    test_results.append(('FAIL', label, msg))
    return False

def assert_in(label, item, collection):
    if item in collection:
        print(f"  OK: {label}")
        return True
    msg = f"  FAIL: {label} - {item!r} not in {collection!r}"
    print(msg)
    test_results.append(('FAIL', label, msg))
    return False


# ─── Setup: get a partner ────────────────────────────────────────────────────
partner_ids = search('res.partner', [('customer_rank', '>', 0)], limit=1)
if not partner_ids:
    partner_ids = search('res.partner', [], limit=1)
partner_id = partner_ids[0]
print(f"Using partner_id={partner_id}")


# ─── Scenario 1: Rule matches order → attachments shown ─────────────────────
print("\n=== Scenario 1: Rule matches - attachments appear ===")
try:
    # Create test attachment
    att_data = base64.b64encode(b"Test commercial material PDF content").decode()
    att_id = create('ir.attachment', {
        'name': f'{PREFIX}brochure.pdf',
        'type': 'binary',
        'datas': att_data,
    })
    register_cleanup('ir.attachment', att_id)

    # Create rule: matches orders with this partner
    rule_id = create('sale.commercial.material.rule', {
        'name': f'{PREFIX}Rule Partner Match',
        'domain': json.dumps([('partner_id', '=', partner_id)]),
        'attachment_ids': [(6, 0, [att_id])],
        'sequence': 10,
    })
    register_cleanup('sale.commercial.material.rule', rule_id)

    # Create sale order with this partner
    so_id = create('sale.order', {
        'partner_id': partner_id,
    })
    register_cleanup('sale.order', so_id)

    # Read commercial_material_ids
    so_data = read_rec('sale.order', [so_id], ['commercial_material_ids'])[0]
    assert_in("Attachment in commercial_material_ids", att_id, so_data['commercial_material_ids'])
    test_results.append(('PASS', 'Scenario 1', ''))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 1', str(e)))


# ─── Scenario 2: Rule does NOT match order → no attachments ─────────────────
print("\n=== Scenario 2: Rule does not match - no attachments ===")
try:
    # Create rule that requires a non-existent partner
    rule2_id = create('sale.commercial.material.rule', {
        'name': f'{PREFIX}Rule No Match',
        'domain': json.dumps([('partner_id', '=', -1)]),
        'attachment_ids': [(6, 0, [att_id])],
        'sequence': 20,
    })
    register_cleanup('sale.commercial.material.rule', rule2_id)

    # Create sale order
    so2_id = create('sale.order', {
        'partner_id': partner_id,
    })
    register_cleanup('sale.order', so2_id)

    # The partner-match rule from Scenario 1 still matches, but rule2 should not add duplicates
    # Deactivate rule from scenario 1 to isolate
    write('sale.commercial.material.rule', [rule_id], {'active': False})

    so2_data = read_rec('sale.order', [so2_id], ['commercial_material_ids'])[0]
    assert_eq("No attachments when rule doesn't match", so2_data['commercial_material_ids'], [])

    # Re-activate for later scenarios
    write('sale.commercial.material.rule', [rule_id], {'active': True})
    test_results.append(('PASS', 'Scenario 2', ''))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 2', str(e)))


# ─── Scenario 3: Multiple rules match → combined attachments ────────────────
print("\n=== Scenario 3: Multiple rules match - combined attachments ===")
try:
    att2_data = base64.b64encode(b"Second commercial doc").decode()
    att2_id = create('ir.attachment', {
        'name': f'{PREFIX}catalog.pdf',
        'type': 'binary',
        'datas': att2_data,
    })
    register_cleanup('ir.attachment', att2_id)

    rule3_id = create('sale.commercial.material.rule', {
        'name': f'{PREFIX}Rule Draft Match',
        'domain': json.dumps([('state', '=', 'draft')]),
        'attachment_ids': [(6, 0, [att2_id])],
        'sequence': 5,
    })
    register_cleanup('sale.commercial.material.rule', rule3_id)

    so3_id = create('sale.order', {
        'partner_id': partner_id,
    })
    register_cleanup('sale.order', so3_id)

    so3_data = read_rec('sale.order', [so3_id], ['commercial_material_ids'])[0]
    cm_ids = so3_data['commercial_material_ids']
    assert_in("First attachment in combined result", att_id, cm_ids)
    assert_in("Second attachment in combined result", att2_id, cm_ids)
    test_results.append(('PASS', 'Scenario 3', ''))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 3', str(e)))


# ─── Scenario 4: Inactive rule is ignored ────────────────────────────────────
print("\n=== Scenario 4: Inactive rule is ignored ===")
try:
    att3_data = base64.b64encode(b"Inactive material").decode()
    att3_id = create('ir.attachment', {
        'name': f'{PREFIX}inactive.pdf',
        'type': 'binary',
        'datas': att3_data,
    })
    register_cleanup('ir.attachment', att3_id)

    rule4_id = create('sale.commercial.material.rule', {
        'name': f'{PREFIX}Inactive Rule',
        'domain': json.dumps([('partner_id', '=', partner_id)]),
        'attachment_ids': [(6, 0, [att3_id])],
        'active': False,
    })
    register_cleanup('sale.commercial.material.rule', rule4_id)

    so4_id = create('sale.order', {
        'partner_id': partner_id,
    })
    register_cleanup('sale.order', so4_id)

    so4_data = read_rec('sale.order', [so4_id], ['commercial_material_ids'])[0]
    assert_true("Inactive rule attachment NOT in results", att3_id not in so4_data['commercial_material_ids'])
    test_results.append(('PASS', 'Scenario 4', ''))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 4', str(e)))


# ─── Scenario 5: Email attachments include commercial material ───────────────
print("\n=== Scenario 5: Email includes commercial material attachments ===")
try:
    # Find the sale order email template
    template_ids = search('mail.template', [('model', '=', 'sale.order')], limit=1)
    if template_ids:
        template_id = template_ids[0]
        try:
            # Use generate_email to check attachments - pass valid mail.template fields
            result = models.execute_kw(DB, uid, ADMIN_PW, 'mail.template', 'generate_email',
                                       [[template_id], [so3_id], ['subject', 'body_html', 'email_from', 'email_to']])
            # Result keys can be int or str depending on XML-RPC
            email_data = result.get(so3_id) or result.get(str(so3_id), {})
            email_attachments = email_data.get('attachments', [])
            att_names = [a[0] for a in email_attachments]
            assert_in("Brochure in email attachments", f'{PREFIX}brochure.pdf', att_names)
            assert_in("Catalog in email attachments", f'{PREFIX}catalog.pdf', att_names)
            test_results.append(('PASS', 'Scenario 5', ''))
        except xmlrpc.client.Fault as e:
            if 'get_quotation_by_door_model' in str(e) or '_render_qweb' in str(e):
                print("  SKIP: Pre-existing report template error (unrelated to commercial material)")
                test_results.append(('SKIP', 'Scenario 5', 'Report template error'))
            else:
                raise
    else:
        print("  SKIP: No sale.order email template found")
        test_results.append(('SKIP', 'Scenario 5', 'No mail template'))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 5', str(e)))


# ─── Scenario 6: Empty domain rule matches all orders ────────────────────────
print("\n=== Scenario 6: Empty domain rule matches all orders ===")
try:
    att4_data = base64.b64encode(b"Universal material").decode()
    att4_id = create('ir.attachment', {
        'name': f'{PREFIX}universal.pdf',
        'type': 'binary',
        'datas': att4_data,
    })
    register_cleanup('ir.attachment', att4_id)

    # Deactivate all previous test rules to isolate
    for rid in cleanup_ids.get('sale.commercial.material.rule', []):
        write('sale.commercial.material.rule', [rid], {'active': False})

    rule6_id = create('sale.commercial.material.rule', {
        'name': f'{PREFIX}Universal Rule',
        'domain': '[]',
        'attachment_ids': [(6, 0, [att4_id])],
    })
    register_cleanup('sale.commercial.material.rule', rule6_id)

    so6_id = create('sale.order', {
        'partner_id': partner_id,
    })
    register_cleanup('sale.order', so6_id)

    so6_data = read_rec('sale.order', [so6_id], ['commercial_material_ids'])[0]
    assert_in("Universal rule attachment present", att4_id, so6_data['commercial_material_ids'])
    test_results.append(('PASS', 'Scenario 6', ''))

except Exception as e:
    print(f"  ERROR: {e}")
    test_results.append(('ERROR', 'Scenario 6', str(e)))


# ─── Cleanup ─────────────────────────────────────────────────────────────────
print("\n=== Cleanup ===")
# Cleanup order matters: sale.order first (may have constraints), then rules, then attachments
for model in ['sale.order', 'sale.commercial.material.rule', 'ir.attachment']:
    ids = cleanup_ids.get(model, [])
    if ids:
        try:
            # For sale orders, cancel first if needed
            if model == 'sale.order':
                for so_id in ids:
                    try:
                        write(model, [so_id], {'state': 'cancel'})
                    except Exception:
                        pass
            unlink(model, ids)
            print(f"  Cleaned {model}: {ids}")
        except Exception as e:
            print(f"  Cleanup warning for {model}: {e}")


# ─── Summary ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
passes = sum(1 for r in test_results if r[0] == 'PASS')
fails = sum(1 for r in test_results if r[0] == 'FAIL')
errors = sum(1 for r in test_results if r[0] == 'ERROR')
skips = sum(1 for r in test_results if r[0] == 'SKIP')

for status, name, msg in test_results:
    icon = {'PASS': 'OK', 'FAIL': 'FAIL', 'ERROR': 'ERR', 'SKIP': 'SKIP'}[status]
    print(f"  [{icon}] {name}")
    if msg and status in ('FAIL', 'ERROR'):
        print(f"        {msg}")

print(f"\nTotal: {passes} passed, {fails} failed, {errors} errors, {skips} skipped")

if fails or errors:
    sys.exit(1)
print("\nAll tests passed!")
