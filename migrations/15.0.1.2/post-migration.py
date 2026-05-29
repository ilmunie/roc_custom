import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Corrige el estimado de la visita (estimated_visit_revenue) a valor CON
    IVA para las visitas PENDIENTES (no terminadas ni canceladas).

    Desde 15.0.1.1 expected_revenue paso a calcularse SIN IVA y, por error, la
    pestaña de visita (importe que ve y cobra el operario) quedo sincronizada
    con ese valor sin IVA. A partir de 15.0.1.2 el estimado vuelve a llevar IVA.

    Aqui se reparan los registros existentes pendientes de cobro. Solo se tocan
    los que quedaron auto-sincronizados con el valor sin IVA del bug
    (estimated == expected_revenue, sin IVA): asi se preservan los importes
    ajustados a mano a nivel de aviso. Escribir sobre el schedule propaga el
    valor al technical.job (campo related stored).
    """
    if not version:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})

    schedules = env['technical.job.schedule'].search(
        [('job_status', 'not in', ('done', 'cancel'))])

    fixed_sched = fixed_source = 0
    for sched in schedules:
        if not sched.res_model or not sched.res_id or sched.res_model not in env:
            continue
        source = env[sched.res_model].browse(sched.res_id).exists()
        # Solo origenes con ordenes de venta y el helper con-IVA (crm.lead).
        if not source or not hasattr(source, '_get_visit_amount_with_tax'):
            continue
        if not source.order_ids:
            continue

        amount = source._get_visit_amount_with_tax()      # CON IVA
        if not amount:
            continue
        no_tax = source.expected_revenue or 0.0           # SIN IVA (valor del bug)

        # Schedule: corregir solo si quedo con el valor sin IVA auto-sincronizado.
        if float_compare(sched.estimated_visit_revenue, no_tax, precision_digits=2) == 0 \
                and float_compare(sched.estimated_visit_revenue, amount, precision_digits=2) != 0:
            sched.estimated_visit_revenue = amount
            fixed_sched += 1

        # Aviso de origen (lead): mismo criterio.
        if float_compare(source.estimated_visit_revenue, no_tax, precision_digits=2) == 0 \
                and float_compare(source.estimated_visit_revenue, amount, precision_digits=2) != 0:
            source.estimated_visit_revenue = amount
            fixed_source += 1

    _logger.info(
        "roc_custom post-migration 15.0.1.2: schedules corregidos=%s, "
        "avisos origen corregidos=%s (visitas pendientes evaluadas=%s)",
        fixed_sched, fixed_source, len(schedules))
