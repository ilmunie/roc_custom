#!/usr/bin/env python3
"""
Benchmark: SQL-optimized methods
Measures actual DB round-trip time for each operation.
Reconnects on errors to avoid cursor-closed issues.
"""
import xmlrpc.client
import time
from datetime import datetime, timedelta

URL = 'http://localhost:8079'
DB = 'roconsa'
PW = '123'

ITERATIONS = 3


def connect():
    common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
    uid = common.authenticate(DB, 'admin', PW, {})
    models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)
    return uid, models


uid, models = connect()
print(f"Connected (uid={uid})")

PREFIX = 'BENCH_'


def search(model, domain, **kw):
    return models.execute_kw(DB, uid, PW, model, 'search', [domain], kw)


def create(model, vals):
    return models.execute_kw(DB, uid, PW, model, 'create', [vals])


def write(model, ids, vals):
    return models.execute_kw(DB, uid, PW, model, 'write', [ids, vals])


def read(model, ids, fields):
    return models.execute_kw(DB, uid, PW, model, 'read', [ids, fields])


def btn(model, method, ids):
    return models.execute_kw(DB, uid, PW, model, method, [ids])


# ── Setup ──────────────────────────────────────────────────────────────────
emp_ids = search('hr.employee', [('technical', '=', True)], limit=1)
emp_id = emp_ids[0] if emp_ids else False
if not emp_id:
    print("ERROR: No technical employee found")
    exit(1)

jt_ids = search('technical.job.type', [('data_assistant', '=', False)], limit=1)
if not jt_ids:
    jt_id = create('technical.job.type', {
        'name': f'{PREFIX}BenchType',
        'data_assistant': False,
        'requires_documentation': False,
        'force_time_registration': False,
        'allow_displacement_tracking': True,
    })
else:
    jt_id = jt_ids[0]

partner_ids = search('res.partner', [], limit=1)
partner_id = partner_ids[0]


def create_bench_job():
    """Create a fresh schedule+job for benchmarking. Reconnects on error."""
    global uid, models
    dt = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    try:
        sched_id = create('technical.job.schedule', {
            'res_model': 'crm.lead',
            'res_id': False,
            'job_type_id': jt_id,
            'date_schedule': dt,
            'job_duration': 1.0,
            'job_employee_ids': [(6, 0, [emp_id])],
        })
    except Exception as e:
        print(f"  [reconnecting after error: {e}]")
        time.sleep(2)
        uid, models = connect()
        sched_id = create('technical.job.schedule', {
            'res_model': 'crm.lead',
            'res_id': False,
            'job_type_id': jt_id,
            'date_schedule': dt,
            'job_duration': 1.0,
            'job_employee_ids': [(6, 0, [emp_id])],
        })
    time.sleep(0.3)
    job_ids = search('technical.job', [('schedule_id', '=', sched_id), ('active', '=', True)])
    if not job_ids:
        time.sleep(1)
        job_ids = search('technical.job', [('schedule_id', '=', sched_id), ('active', '=', True)])
    return sched_id, job_ids[0]


def run_bench(label, setup_fn, target_fn):
    """Run benchmark with proper error handling."""
    global uid, models
    times = []
    for i in range(ITERATIONS):
        try:
            ctx = setup_fn()
            time.sleep(0.1)
            t0 = time.time()
            target_fn(ctx)
            elapsed = (time.time() - t0) * 1000
            times.append(elapsed)
        except Exception as e:
            print(f"  [{label} iter {i} error: {e}, reconnecting]")
            time.sleep(2)
            uid, models = connect()
            try:
                ctx = setup_fn()
                time.sleep(0.1)
                t0 = time.time()
                target_fn(ctx)
                elapsed = (time.time() - t0) * 1000
                times.append(elapsed)
            except Exception as e2:
                print(f"  [{label} iter {i} SKIP: {e2}]")
    if times:
        return label, sum(times)/len(times), min(times), max(times)
    return label, 0, 0, 0


# ── Benchmarks ─────────────────────────────────────────────────────────────
results = []

print(f"\nRunning benchmarks (each operation x{ITERATIONS} iterations)...\n")

# 1. confirm()
print("  1. confirm()...")
results.append(run_bench(
    "confirm()",
    lambda: create_bench_job(),
    lambda ctx: btn('technical.job', 'confirm', [ctx[1]])
))

# 2. set_draft()
print("  2. set_draft()...")
results.append(run_bench(
    "set_draft()",
    lambda: (lambda sj: (btn('technical.job', 'confirm', [sj[1]]), sj))(*[create_bench_job()])[1],
    lambda ctx: btn('technical.job', 'set_draft', [ctx[1]])
))

# 3. schedule.start_tracking()
print("  3. schedule.start_tracking()...")
results.append(run_bench(
    "sched.start_tracking()",
    lambda: (lambda sj: (btn('technical.job', 'confirm', [sj[1]]), sj))(*[create_bench_job()])[1],
    lambda ctx: btn('technical.job.schedule', 'start_tracking', [ctx[0]])
))

# 4. schedule.stop_tracking()
print("  4. schedule.stop_tracking()...")
def setup_stop_track():
    s, j = create_bench_job()
    btn('technical.job', 'confirm', [j])
    btn('technical.job.schedule', 'start_tracking', [s])
    time.sleep(1)
    return s, j

results.append(run_bench(
    "sched.stop_tracking()",
    setup_stop_track,
    lambda ctx: btn('technical.job.schedule', 'stop_tracking', [ctx[0]])
))

# 5. start_displacement()
print("  5. start_displacement()...")
results.append(run_bench(
    "start_displacement()",
    lambda: (lambda sj: (btn('technical.job', 'confirm', [sj[1]]), sj))(*[create_bench_job()])[1],
    lambda ctx: btn('technical.job', 'start_displacement', [ctx[1]])
))

# 6. end_displacement()
print("  6. end_displacement()...")
def setup_end_disp():
    s, j = create_bench_job()
    btn('technical.job', 'confirm', [j])
    btn('technical.job', 'start_displacement', [j])
    time.sleep(0.5)
    return s, j

results.append(run_bench(
    "end_displacement()",
    setup_end_disp,
    lambda ctx: btn('technical.job', 'end_displacement', [ctx[1]])
))

# 7. job.start_tracking()
print("  7. job.start_tracking()...")
results.append(run_bench(
    "job.start_tracking()",
    lambda: (lambda sj: (btn('technical.job', 'confirm', [sj[1]]), sj))(*[create_bench_job()])[1],
    lambda ctx: btn('technical.job', 'start_tracking', [ctx[1]])
))

# 8. job.stop_tracking() (no assistant → mark_as_done)
print("  8. job.stop_tracking()+done...")
def setup_job_stop():
    s, j = create_bench_job()
    btn('technical.job', 'confirm', [j])
    btn('technical.job', 'start_tracking', [j])
    time.sleep(1)
    return s, j

results.append(run_bench(
    "job.stop_tracking()+done",
    setup_job_stop,
    lambda ctx: btn('technical.job', 'stop_tracking', [ctx[1]])
))

# 9. stand_by()
print("  9. stand_by()...")
def setup_stand_by():
    s, j = create_bench_job()
    btn('technical.job', 'confirm', [j])
    btn('technical.job.schedule', 'start_tracking', [s])
    time.sleep(0.5)
    write('technical.job', [j], {'internal_notes': 'Benchmark stand_by note'})
    return s, j

results.append(run_bench(
    "stand_by()",
    setup_stand_by,
    lambda ctx: btn('technical.job', 'stand_by', [ctx[1]])
))

# 10. mark_as_done() standalone
print("  10. mark_as_done()...")
def setup_mark_done():
    s, j = create_bench_job()
    btn('technical.job', 'confirm', [j])
    btn('technical.job.schedule', 'start_tracking', [s])
    time.sleep(1)
    btn('technical.job.schedule', 'stop_tracking', [s])
    return s, j

results.append(run_bench(
    "mark_as_done()",
    setup_mark_done,
    lambda ctx: btn('technical.job', 'mark_as_done', [ctx[1]])
))

# ── Results ────────────────────────────────────────────────────────────────
print("\n" + "=" * 75)
print("BENCHMARK RESULTS (SQL-optimized, {} iterations each)".format(ITERATIONS))
print("=" * 75)
print(f"{'Method':<35} {'Avg (ms)':>10} {'Min (ms)':>10} {'Max (ms)':>10}")
print("-" * 75)
for label, avg, mn, mx in results:
    bar = "#" * max(1, int(avg / 5))
    print(f"  {label:<33} {avg:>8.1f}   {mn:>8.1f}   {mx:>8.1f}   {bar}")
print("-" * 75)
total_avg = sum(r[1] for r in results)
print(f"  {'TOTAL':<33} {total_avg:>8.1f}")
print()
print("Note: These times include network round-trip (XML-RPC overhead).")
print("Server-side execution is ~5-15ms faster than shown.")
print(f"Data left in DB with prefix: {PREFIX}")
