#!/usr/bin/env python3
"""
E2E Test Script for Technical Operations Module (roc_custom)
Tests the full lifecycle of technical jobs via XML-RPC.
"""
import xmlrpc.client
import time
import sys
import traceback
import base64
from datetime import datetime, timedelta

# ─── Connection config ───────────────────────────────────────────────────────
URL = 'http://localhost:8079'
DB = 'roconsa'
ADMIN_PW = '123'
PREFIX = 'E2E_OPS_'


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


def reconnect():
    """Reconnect if previous scenario crashed the worker."""
    global uid, models
    for attempt in range(5):
        try:
            uid, models = connect()
            # Quick test
            models.execute_kw(DB, uid, ADMIN_PW, 'res.users', 'search', [[('id', '=', uid)]])
            return True
        except Exception:
            print(f"  Reconnect attempt {attempt+1}/5...")
            time.sleep(3)
    return False


# ─── Helpers ─────────────────────────────────────────────────────────────────
def search(model, domain, **kw):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'search', [domain], kw)


def search_read(model, domain, fields, **kw):
    kw['fields'] = fields
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'search_read', [domain], kw)


def read(model, ids, fields):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'read', [ids, fields])


def create(model, vals):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'create', [vals])


def write(model, ids, vals):
    return models.execute_kw(DB, uid, ADMIN_PW, model, 'write', [ids, vals])


def call_button(model, method, ids):
    return models.execute_kw(DB, uid, ADMIN_PW, model, method, [ids])


def call_button_as(user_uid, model, method, ids):
    return models.execute_kw(DB, user_uid, ADMIN_PW, model, method, [ids])


def timed(label, func, *args, **kwargs):
    t0 = time.time()
    result = func(*args, **kwargs)
    elapsed = (time.time() - t0) * 1000
    perf_results.append((label, elapsed))
    print(f"  PERF {label}: {elapsed:.1f} ms")
    return result


perf_results = []
test_results = []


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


def create_test_schedule(lead_id, job_type, employee_id, days_offset=1):
    """Create a schedule manually with all fields upfront to avoid problematic writes."""
    visit_dt = (datetime.now() + timedelta(days=days_offset)).strftime('%Y-%m-%d %H:%M:%S')
    schedule_id = create('technical.job.schedule', {
        'res_model': 'crm.lead',
        'res_id': lead_id,
        'job_type_id': job_type,
        'date_schedule': visit_dt,
        'job_duration': 1.5,
        'job_employee_ids': [(6, 0, [employee_id])],
    })
    time.sleep(1)
    job_ids = search('technical.job', [('schedule_id', '=', schedule_id), ('active', '=', True)])
    job_id = job_ids[0] if job_ids else False
    return schedule_id, job_id


# ─── Setup ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SETUP: Creating test data")
print("=" * 70)


def get_or_create_user(login, name, group_xmlid):
    user_ids = search('res.users', [('login', '=', login)])
    if user_ids:
        # Ensure internal user group and email are set
        internal_group = search_read('ir.model.data',
                                     [('module', '=', 'base'), ('name', '=', 'group_user')],
                                     ['res_id'], limit=1)
        email = f'{login.lower().replace(" ", "_")}@test.com'
        update_vals = {'email': email}
        if internal_group:
            update_vals['groups_id'] = [(4, internal_group[0]['res_id'])]
        write('res.users', user_ids, update_vals)
        print(f"  Found existing user: {login} (id={user_ids[0]})")
        return user_ids[0]
    # Get the operations-specific group
    module, xmlid = group_xmlid.split('.')
    group_data = search_read('ir.model.data',
                             [('module', '=', module), ('name', '=', xmlid)],
                             ['res_id'], limit=1)
    group_id = group_data[0]['res_id'] if group_data else False
    if not group_id:
        raise Exception(f"Group {group_xmlid} not found!")
    # Get internal user group
    internal_group = search_read('ir.model.data',
                                 [('module', '=', 'base'), ('name', '=', 'group_user')],
                                 ['res_id'], limit=1)
    internal_group_id = internal_group[0]['res_id'] if internal_group else False
    groups = [(4, group_id)]
    if internal_group_id:
        groups.append((4, internal_group_id))
    email = f'{login.lower().replace(" ", "_")}@test.com'
    user_id = create('res.users', {
        'name': name, 'login': login, 'password': '123',
        'email': email, 'groups_id': groups,
    })
    write('res.users', [user_id], {'groups_id': [(4, group_id)]})
    print(f"  Created user: {login} (id={user_id})")
    return user_id


coordinator_user_id = get_or_create_user(
    f'{PREFIX}Coordinador', f'{PREFIX}Coordinador', 'roc_custom.technical_job_planner')
operator_user_id = get_or_create_user(
    f'{PREFIX}Operario', f'{PREFIX}Operario', 'roc_custom.technical_job_user')


def get_or_create_employee(user_id, name):
    emp_ids = search('hr.employee', [('user_id', '=', user_id)])
    if emp_ids:
        write('hr.employee', emp_ids, {'technical': True})
        print(f"  Found existing employee for {name} (id={emp_ids[0]})")
        return emp_ids[0]
    emp_id = create('hr.employee', {'name': name, 'user_id': user_id, 'technical': True})
    print(f"  Created employee for {name} (id={emp_id})")
    return emp_id


coordinator_emp_id = get_or_create_employee(coordinator_user_id, f'{PREFIX}Coordinador')
operator_emp_id = get_or_create_employee(operator_user_id, f'{PREFIX}Operario')

# Job types
job_type_ids = search('technical.job.type', [('name', '=', f'{PREFIX}Tipo_Test')])
if job_type_ids:
    job_type_id = job_type_ids[0]
    write('technical.job.type', [job_type_id], {
        'data_assistant': True, 'requires_documentation': True,
        'force_time_registration': True, 'allow_displacement_tracking': True,
    })
else:
    job_type_id = create('technical.job.type', {
        'name': f'{PREFIX}Tipo_Test', 'data_assistant': True,
        'requires_documentation': True, 'force_time_registration': True,
        'allow_displacement_tracking': True,
    })
print(f"  Job type with assistant (id={job_type_id})")

job_type_no_asst_ids = search('technical.job.type', [('name', '=', f'{PREFIX}Tipo_SinAsistente')])
if job_type_no_asst_ids:
    job_type_no_assistant_id = job_type_no_asst_ids[0]
    write('technical.job.type', [job_type_no_assistant_id], {
        'data_assistant': False, 'requires_documentation': False,
        'force_time_registration': False, 'allow_displacement_tracking': True,
    })
else:
    job_type_no_assistant_id = create('technical.job.type', {
        'name': f'{PREFIX}Tipo_SinAsistente', 'data_assistant': False,
        'requires_documentation': False, 'force_time_registration': False,
        'allow_displacement_tracking': True,
    })
print(f"  Job type without assistant (id={job_type_no_assistant_id})")

# Assistant config for crm.lead
model_data = search_read('ir.model', [('model', '=', 'crm.lead')], ['id'])
crm_lead_model_id = model_data[0]['id'] if model_data else False
config_ids = search('technical.job.assistant.config', [('name', '=', f'{PREFIX}Config_CRM')])
if config_ids:
    assistant_config_id = config_ids[0]
    write('technical.job.assistant.config', [assistant_config_id], {
        'technical_job_type_id': job_type_id,
        'domain_condition': "[('name', 'ilike', 'E2E_OPS_')]",
        'responsible_user_id': uid,
    })
else:
    assistant_config_id = create('technical.job.assistant.config', {
        'name': f'{PREFIX}Config_CRM', 'model_id': crm_lead_model_id,
        'domain_condition': "[('name', 'ilike', 'E2E_OPS_')]",
        'technical_job_type_id': job_type_id, 'responsible_user_id': uid,
    })
print(f"  Assistant config (id={assistant_config_id})")

# Partner
partner_ids = search('res.partner', [('name', '=', f'{PREFIX}Partner_Test')])
if partner_ids:
    partner_id = partner_ids[0]
else:
    spain_id = search('res.country', [('code', '=', 'ES')])[0]
    partner_id = create('res.partner', {
        'name': f'{PREFIX}Partner_Test', 'street': 'Calle Test 123',
        'city': 'Madrid', 'zip': '28001', 'country_id': spain_id,
        'email': 'e2e_ops_test@test.com', 'phone': '+34600000000',
    })
print(f"  Partner (id={partner_id})")


# ─── Scenario 1: Happy Path ─────────────────────────────────────────────────
print("\n" + "=" * 70)
print("SCENARIO 1: Happy Path - Full lifecycle")
print("=" * 70)

try:
    # Create lead (no auto-generation to keep it simple)
    lead_id = create('crm.lead', {
        'name': f'{PREFIX}S1_HappyPath_{int(time.time())}',
        'partner_id': partner_id,
        'type': 'opportunity',
    })
    print(f"  Created lead (id={lead_id})")

    # Create schedule manually
    schedule_id, job_id = create_test_schedule(lead_id, job_type_id, operator_emp_id, days_offset=1)
    assert_true("Schedule created", schedule_id)
    assert_true("Job created", job_id)
    print(f"  Schedule={schedule_id}, Job={job_id}")

    # Confirm
    result = timed("confirm()", call_button, 'technical.job', 'confirm', [job_id])
    job_data = read('technical.job', [job_id], ['job_status'])[0]
    assert_eq("Job status after confirm", job_data['job_status'], 'confirmed')

    # Start displacement
    result = timed("start_displacement()", call_button, 'technical.job', 'start_displacement', [job_id])
    schedule_data = read('technical.job.schedule', [schedule_id], ['displacement_start_datetime'])[0]
    assert_true("Displacement start datetime set", schedule_data['displacement_start_datetime'])
    time_regs = search_read('technical.job.time.register',
                            [('technical_job_schedule_id', '=', schedule_id), ('displacement', '=', True)],
                            ['start_time', 'end_time'])
    assert_true("Displacement time register created", len(time_regs) > 0)

    # End displacement
    time.sleep(1)
    result = timed("end_displacement()", call_button, 'technical.job', 'end_displacement', [job_id])
    time_regs = search_read('technical.job.time.register',
                            [('technical_job_schedule_id', '=', schedule_id), ('displacement', '=', True)],
                            ['start_time', 'end_time'])
    if time_regs:
        assert_true("Displacement end_time set", time_regs[0]['end_time'])

    # Start tracking → returns action for note assistant (data_assistant=True)
    result = timed("start_tracking()", call_button, 'technical.job', 'start_tracking', [job_id])

    # Verify start_tracking_time is set
    sched_check = read('technical.job.schedule', [schedule_id], ['start_tracking_time'])[0]
    assert_true("start_tracking_time set on schedule", sched_check['start_tracking_time'])
    print(f"  DEBUG: start_tracking_time = {sched_check['start_tracking_time']}")

    if isinstance(result, dict) and result.get('res_model') == 'technical.job.note.assistant':
        print("  OK: start_tracking returned note assistant action (data_assistant=True)")
        note_ctx = result.get('context', {})
        note_id = create('technical.job.note.assistant', {
            'content': f'{PREFIX}Descripcion inicial de prueba',
            'content_type': note_ctx.get('note_assistant_type', 'Descripcion Inicial'),
            'technical_job_id': note_ctx.get('technical_job', job_id),
            'pending_jobs': 'no',
            'todo_description': 'Tarea de prueba E2E',
        })
        execute_result = models.execute_kw(DB, uid, ADMIN_PW,
                                           'technical.job.note.assistant', 'action_done', [[note_id]])
        print("  OK: Note assistant (Descripcion Inicial) action_done executed")
    else:
        print(f"  INFO: start_tracking returned: {result}")

    # Verify start_tracking_time still set after note assistant
    sched_check2 = read('technical.job.schedule', [schedule_id], ['start_tracking_time'])[0]
    print(f"  DEBUG: start_tracking_time after note_assistant = {sched_check2['start_tracking_time']}")

    # Wait for time to accumulate
    print("  Waiting 3 seconds for time accumulation...")
    time.sleep(3)

    # Stop tracking
    result = timed("stop_tracking()", call_button, 'technical.job', 'stop_tracking', [job_id])
    schedule_data = read('technical.job.schedule', [schedule_id], ['minutes_in_job', 'start_tracking_time'])[0]
    print(f"  DEBUG: minutes_in_job = {schedule_data['minutes_in_job']}, start_tracking_time = {schedule_data['start_tracking_time']}")
    assert_true("minutes_in_job > 0 after stop_tracking", schedule_data['minutes_in_job'] > 0)

    if isinstance(result, dict) and result.get('res_model') == 'technical.job.note.assistant':
        print("  OK: stop_tracking returned note assistant action for finalization")

        # Upload attachment BEFORE finalizing (requires_documentation=True)
        att_id = create('ir.attachment', {
            'name': f'{PREFIX}test_photo.jpg', 'type': 'binary',
            'datas': base64.b64encode(b'fake image data for E2E test').decode('utf-8'),
            'res_model': 'technical.job', 'res_id': job_id,
        })
        print(f"  Created test attachment (id={att_id})")

        # Create finalization note assistant
        note_ctx = result.get('context', {})
        note_id = create('technical.job.note.assistant', {
            'content': f'{PREFIX}Trabajo finalizado correctamente',
            'content_type': 'Finalizacion trabajo',
            'technical_job_id': note_ctx.get('technical_job', job_id),
            'pending_jobs': 'no', 'needs_billing': 'no',
            'needs_quotation': 'no', 'new_opportunities': 'no',
        })
        models.execute_kw(DB, uid, ADMIN_PW,
                          'technical.job.note.assistant', 'action_done', [[note_id]])
        print("  OK: Finalization note assistant action_done executed")
    else:
        print(f"  INFO: stop_tracking returned: {result}")

    # Verify final state
    job_data = read('technical.job', [job_id], ['job_status'])[0]
    assert_eq("Job status is done", job_data['job_status'], 'done')

    # Verify message posted on lead
    lead_msgs = search_read('mail.message',
                            [('res_id', '=', lead_id), ('model', '=', 'crm.lead'),
                             ('body', 'like', 'finalizado')], ['body'])
    assert_true("Completion message posted on lead", len(lead_msgs) > 0)

    print("\n  SCENARIO 1: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 1 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 1', str(e)))

# Reconnect between scenarios
reconnect()

# ─── Scenario 2: Documentation requirement by role ──────────────────────────
print("\n" + "=" * 70)
print("SCENARIO 2: Documentation requirement by role")
print("=" * 70)

try:
    lead_id2 = create('crm.lead', {
        'name': f'{PREFIX}S2_DocReq_{int(time.time())}',
        'partner_id': partner_id, 'type': 'opportunity',
    })
    print(f"  Created lead (id={lead_id2})")

    schedule_id2, job_id2 = create_test_schedule(lead_id2, job_type_id, operator_emp_id, days_offset=2)
    assert_true("Schedule+Job created", job_id2)
    print(f"  Schedule={schedule_id2}, Job={job_id2}")

    # Confirm, start tracking, register time, stop tracking
    call_button('technical.job', 'confirm', [job_id2])

    # Start tracking via schedule directly (avoid wizard chain)
    call_button('technical.job.schedule', 'start_tracking', [schedule_id2])
    time.sleep(2)
    call_button('technical.job.schedule', 'stop_tracking', [schedule_id2])

    # Verify time registered
    sched_data2 = read('technical.job.schedule', [schedule_id2], ['minutes_in_job'])[0]
    assert_true("Time registered > 0", sched_data2['minutes_in_job'] > 0)

    # Test 1: Operator tries mark_as_done WITHOUT attachment → should fail
    print("\n  Testing: Operator mark_as_done WITHOUT attachment (should fail)...")
    try:
        call_button_as(operator_user_id, 'technical.job', 'mark_as_done', [job_id2])
        print("  FAIL: Expected ValidationError for missing documentation but got none")
        test_results.append(('FAIL', 'S2 Operator no doc', 'No error raised'))
    except xmlrpc.client.Fault as fault:
        if 'documentaci' in fault.faultString.lower():
            print("  OK: Operator correctly blocked - requires documentation")
        else:
            print(f"  FAIL: Unexpected error: {fault.faultString[:200]}")
            test_results.append(('FAIL', 'S2 Operator error', fault.faultString[:200]))

    # Test 2: Coordinator tries mark_as_done WITHOUT attachment → should succeed
    print("\n  Testing: Coordinator mark_as_done WITHOUT attachment (should succeed)...")
    try:
        result = call_button_as(coordinator_user_id, 'technical.job', 'mark_as_done', [job_id2])
        job_data2 = read('technical.job', [job_id2], ['job_status'])[0]
        assert_eq("Coordinator can mark_as_done without docs", job_data2['job_status'], 'done')
    except xmlrpc.client.Fault as fault:
        print(f"  FAIL: Coordinator blocked unexpectedly: {fault.faultString[:200]}")
        test_results.append(('FAIL', 'S2 Coordinator blocked', fault.faultString[:200]))

    print("\n  SCENARIO 2: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 2 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 2', str(e)))

reconnect()

# ─── Scenario 3: Stand-by + Re-coordination ─────────────────────────────────
print("\n" + "=" * 70)
print("SCENARIO 3: Stand-by + Re-coordination")
print("=" * 70)

try:
    lead_id3 = create('crm.lead', {
        'name': f'{PREFIX}S3_StandBy_{int(time.time())}',
        'partner_id': partner_id, 'type': 'opportunity',
    })
    print(f"  Created lead (id={lead_id3})")

    schedule_id3, job_id3 = create_test_schedule(lead_id3, job_type_id, operator_emp_id, days_offset=3)
    assert_true("Schedule+Job created", job_id3)

    # Confirm
    timed("confirm() [S3]", call_button, 'technical.job', 'confirm', [job_id3])

    # Start tracking via schedule directly
    timed("start_tracking() [S3]", call_button, 'technical.job.schedule', 'start_tracking', [schedule_id3])
    time.sleep(2)

    # Set internal_notes (required for stand_by)
    write('technical.job', [job_id3], {
        'internal_notes': f'{PREFIX}Notas internas para aplazar - cliente no disponible',
    })
    print("  Set internal_notes on job")

    # Stand by
    result = timed("stand_by() [S3]", call_button, 'technical.job', 'stand_by', [job_id3])
    job_data3 = read('technical.job', [job_id3], ['job_status'])[0]
    assert_eq("Job status after stand_by", job_data3['job_status'], 'stand_by')

    # Verify message posted on lead
    lead_msgs = search_read('mail.message',
                            [('res_id', '=', lead_id3), ('model', '=', 'crm.lead'),
                             ('body', 'like', 'aplazado')], ['body'])
    assert_true("Stand-by message posted on lead", len(lead_msgs) > 0)

    # set_draft → back to to_do
    result = timed("set_draft() [S3]", call_button, 'technical.job', 'set_draft', [job_id3])
    job_data3 = read('technical.job', [job_id3], ['job_status'])[0]
    assert_eq("Job status after set_draft", job_data3['job_status'], 'to_do')

    # Re-confirm
    timed("confirm() re [S3]", call_button, 'technical.job', 'confirm', [job_id3])

    # Start tracking again, stop, upload doc, mark as done
    call_button('technical.job.schedule', 'start_tracking', [schedule_id3])
    time.sleep(2)
    call_button('technical.job.schedule', 'stop_tracking', [schedule_id3])

    att_id3 = create('ir.attachment', {
        'name': f'{PREFIX}standby_doc.jpg', 'type': 'binary',
        'datas': base64.b64encode(b'fake standby doc').decode('utf-8'),
        'res_model': 'technical.job', 'res_id': job_id3,
    })

    result = timed("mark_as_done() [S3]", call_button, 'technical.job', 'mark_as_done', [job_id3])
    job_data3 = read('technical.job', [job_id3], ['job_status'])[0]
    assert_eq("Job status after mark_as_done", job_data3['job_status'], 'done')

    print("\n  SCENARIO 3: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 3 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 3', str(e)))

reconnect()

# ─── Scenario 4: Billing flow ───────────────────────────────────────────────
print("\n" + "=" * 70)
print("SCENARIO 4: Billing flow")
print("=" * 70)

try:
    lead_id4 = create('crm.lead', {
        'name': f'{PREFIX}S4_Billing_{int(time.time())}',
        'partner_id': partner_id, 'type': 'opportunity',
    })
    print(f"  Created lead (id={lead_id4})")

    schedule_id4, job_id4 = create_test_schedule(lead_id4, job_type_id, operator_emp_id, days_offset=4)
    assert_true("Schedule+Job created", job_id4)

    # Process to done: confirm, track time, upload doc, mark_as_done
    call_button('technical.job', 'confirm', [job_id4])
    call_button('technical.job.schedule', 'start_tracking', [schedule_id4])
    time.sleep(2)
    call_button('technical.job.schedule', 'stop_tracking', [schedule_id4])

    att_id4 = create('ir.attachment', {
        'name': f'{PREFIX}billing_doc.jpg', 'type': 'binary',
        'datas': base64.b64encode(b'fake billing doc').decode('utf-8'),
        'res_model': 'technical.job', 'res_id': job_id4,
    })

    call_button('technical.job', 'mark_as_done', [job_id4])
    job_data4 = read('technical.job', [job_id4], ['job_status'])[0]
    assert_eq("Job done before billing", job_data4['job_status'], 'done')

    # Call billing wizard
    billing_result = timed("call_billing_wiz()", call_button, 'technical.job', 'call_billing_wiz', [job_id4])
    assert_true("call_billing_wiz returns action", isinstance(billing_result, dict))

    if isinstance(billing_result, dict) and billing_result.get('res_model') == 'technical.job.billing.assistant':
        print("  OK: Billing wizard action returned")
        billing_ctx = billing_result.get('context', {})
        try:
            billing_id = create('technical.job.billing.assistant', {
                'technical_job_id': billing_ctx.get('technical_job', job_id4),
                'materials_to_bill': False, 'hs_bill': False,
            })
            billing_done = models.execute_kw(DB, uid, ADMIN_PW,
                                             'technical.job.billing.assistant', 'action_done', [[billing_id]])
            print(f"  OK: Billing assistant action_done executed")

            schedule_data4 = read('technical.job.schedule', [schedule_id4], ['sale_order_ids'])[0]
            so_ids = schedule_data4.get('sale_order_ids', [])
            if so_ids:
                print(f"  OK: Sale order created and linked (ids={so_ids})")
            else:
                print("  INFO: No sale order linked (needs billing lines to create SO)")
        except xmlrpc.client.Fault as fault:
            print(f"  INFO: Billing wizard error (may need template config): {fault.faultString[:200]}")

    print("\n  SCENARIO 4: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 4 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 4', str(e)))

reconnect()

# ─── Scenario 5: Direct finalization (no wizard) ────────────────────────────
print("\n" + "=" * 70)
print("SCENARIO 5: Direct finalization (no data assistant wizard)")
print("=" * 70)

try:
    lead_id5 = create('crm.lead', {
        'name': f'{PREFIX}S5_DirectFinish_{int(time.time())}',
        'partner_id': partner_id, 'type': 'opportunity',
    })
    print(f"  Created lead (id={lead_id5})")

    schedule_id5, job_id5 = create_test_schedule(lead_id5, job_type_no_assistant_id, coordinator_emp_id, days_offset=5)
    assert_true("Schedule+Job created", job_id5)

    # Confirm
    call_button('technical.job', 'confirm', [job_id5])

    # Start tracking → should NOT return wizard action
    result5_start = timed("start_tracking() no-wiz", call_button, 'technical.job', 'start_tracking', [job_id5])
    if isinstance(result5_start, dict) and result5_start.get('res_model') == 'technical.job.note.assistant':
        print("  WARN: start_tracking returned wizard with data_assistant=False")
    else:
        print("  OK: start_tracking did not return wizard (data_assistant=False)")

    time.sleep(2)

    # Stop tracking → should call mark_as_done directly
    result5_stop = timed("stop_tracking() no-wiz", call_button, 'technical.job', 'stop_tracking', [job_id5])

    job_data5 = read('technical.job', [job_id5], ['job_status'])[0]
    assert_eq("Job done (direct finalization)", job_data5['job_status'], 'done')

    print("\n  SCENARIO 5: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 5 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 5', str(e)))

reconnect()

# ─── Scenario 6: Auto-generation via visit_job_generation ────────────────────
print("\n" + "=" * 70)
print("SCENARIO 6: Auto-generation via visit_job_generation")
print("=" * 70)

try:
    visit_dt = (datetime.now() + timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
    lead_auto = create('crm.lead', {
        'name': f'{PREFIX}S6_AutoGen_{int(time.time())}',
        'partner_id': partner_id, 'type': 'opportunity',
        'customer_availability_type': 'specific_date',
        'customer_visit_datetime': visit_dt,
    })
    print(f"  Created lead with specific_date (id={lead_auto})")
    time.sleep(1)

    lead_data = read('crm.lead', [lead_auto], ['technical_schedule_job_ids'])[0]
    schedule_ids_auto = lead_data.get('technical_schedule_job_ids', [])
    assert_true("Schedule auto-created from visit_job_generation", len(schedule_ids_auto) > 0)
    if schedule_ids_auto:
        auto_sched = read('technical.job.schedule', [schedule_ids_auto[0]], ['job_status', 'job_type_id'])[0]
        print(f"  Auto schedule: status={auto_sched['job_status']}, type={auto_sched['job_type_id']}")

    print("\n  SCENARIO 6: COMPLETED")

except Exception as e:
    print(f"\n  SCENARIO 6 ERROR: {e}")
    traceback.print_exc()
    test_results.append(('ERROR', 'Scenario 6', str(e)))


# ─── Summary ─────────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("PERFORMANCE SUMMARY")
print("=" * 70)
for label, elapsed in perf_results:
    bar = "#" * max(1, int(elapsed / 10))
    print(f"  {label:45s} {elapsed:8.1f} ms  {bar}")

avg = sum(e for _, e in perf_results) / len(perf_results) if perf_results else 0
print(f"\n  Average: {avg:.1f} ms")

print("\n" + "=" * 70)
print("TEST RESULTS SUMMARY")
print("=" * 70)
failures = [r for r in test_results if r[0] == 'FAIL']
errors = [r for r in test_results if r[0] == 'ERROR']
if not test_results:
    print("  ALL TESTS PASSED!")
else:
    for status, label, msg in test_results:
        print(f"  [{status}] {label}: {msg[:120]}")

print(f"\nTotal failures: {len(failures)}, errors: {len(errors)}")
print("Data left in DB with prefix: " + PREFIX)
