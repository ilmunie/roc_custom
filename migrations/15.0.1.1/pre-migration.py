import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Preparacion para el nuevo campo computado stored
    'trigger_sync_opportunity_revenue' en sale.order.

    1) Pre-crea la columna para que Odoo NO dispare el recalculo masivo del
       campo sobre todas las sale.order existentes (lo que pisaria el
       expected_revenue de TODAS las oportunidades, incluso las editadas a
       mano).
    2) Guarda un snapshot del expected_revenue actual de los leads con ordenes
       de venta asociadas, para que la post-migration pueda distinguir los
       valores automaticos de los modificados manualmente.
    """
    if not version:
        return

    cr.execute("""
        ALTER TABLE sale_order
        ADD COLUMN IF NOT EXISTS trigger_sync_opportunity_revenue boolean
    """)

    cr.execute("""
        DROP TABLE IF EXISTS roc_tmp_exprev_snapshot;
        CREATE TABLE roc_tmp_exprev_snapshot AS
        SELECT DISTINCT l.id AS lead_id, l.expected_revenue AS original_value
        FROM crm_lead l
        WHERE EXISTS (
            SELECT 1 FROM sale_order s WHERE s.opportunity_id = l.id
        )
    """)
    cr.execute("SELECT count(*) FROM roc_tmp_exprev_snapshot")
    count = cr.fetchone()[0]
    _logger.info(
        "roc_custom pre-migration 15.0.1.1: columna pre-creada y snapshot de "
        "%s leads con ordenes guardado.", count)
