import logging

from odoo import api, SUPERUSER_ID
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recalcula expected_revenue a valor SIN impuestos solo para los leads
    cuyo valor NO fue modificado manualmente.

    Criterio: un lead se considera "automatico" (recalculable) si su
    expected_revenue original (snapshot tomado en la pre-migration) coincide
    con el calculo VIEJO (con impuestos) que hacia la funcion antes. En ese
    caso se actualiza al nuevo calculo SIN impuestos. Si no coincide, el valor
    fue tocado a mano: se preserva (y se restaura por si el alta del campo
    computado lo hubiera pisado).
    """
    if not version:
        return

    cr.execute("SELECT lead_id, original_value FROM roc_tmp_exprev_snapshot")
    snapshot = {row[0]: (row[1] or 0.0) for row in cr.fetchall()}
    if not snapshot:
        _logger.info("roc_custom post-migration 15.0.1.1: snapshot vacio, nada que hacer.")
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    leads = env['crm.lead'].browse(list(snapshot.keys())).exists()

    updated = restored = skipped = 0
    for lead in leads:
        original = snapshot.get(lead.id, 0.0)

        confirmed = lead.order_ids.filtered(
            lambda x: not x.pos_order_line_ids and x.state in ('done', 'sale'))
        old_amount = sum(confirmed.mapped('amount_total'))       # viejo: CON IVA
        new_amount = sum(confirmed.mapped('amount_untaxed'))     # nuevo: SIN IVA
        pos_ids = []
        for pos_line in lead.order_ids.pos_order_line_ids:
            pos_order = pos_line.order_id
            if pos_order.id not in pos_ids:
                old_amount += pos_order.amount_total
                new_amount += pos_order.amount_total - pos_order.amount_tax
                pos_ids.append(pos_order.id)

        if float_compare(original, old_amount, precision_digits=2) == 0:
            # Valor automatico -> migrar a SIN IVA
            if float_compare(lead.expected_revenue, new_amount, precision_digits=2) != 0:
                lead.expected_revenue = new_amount
                updated += 1
        else:
            # Valor modificado a mano -> preservar / restaurar
            if float_compare(lead.expected_revenue, original, precision_digits=2) != 0:
                lead.expected_revenue = original
                restored += 1
            skipped += 1

    cr.execute("DROP TABLE IF EXISTS roc_tmp_exprev_snapshot")
    _logger.info(
        "roc_custom post-migration 15.0.1.1: recalculados=%s, restaurados=%s, "
        "preservados_manual=%s (total evaluados=%s)",
        updated, restored, skipped, len(leads))
