import base64
import logging
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CrmLeadSendQuotations(models.TransientModel):
    _name = 'crm.lead.send.quotations'
    _description = 'Envío masivo de presupuestos desde oportunidades'

    lead_ids = fields.Many2many('crm.lead', string="Oportunidades")
    order_ids = fields.Many2many('sale.order', string="Presupuestos")
    partner_count = fields.Integer(string="Cantidad de clientes", readonly=True)
    template_id = fields.Many2one(
        'mail.template',
        string="Plantilla de correo",
        domain=[('model', '=', 'sale.order')],
        default=lambda self: self.env.ref(
            'roc_sales.mail_template_sale_partner_without_confirmation', raise_if_not_found=False
        ),
    )
    subject = fields.Char(string="Asunto")
    body = fields.Html(string="Cuerpo del correo")
    order_summary = fields.Html(string="Resumen de presupuestos", readonly=True)

    @api.model
    def default_get(self, field_list):
        res = super().default_get(field_list)
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise UserError(_("Debe seleccionar al menos una oportunidad."))
        leads = self.env['crm.lead'].browse(active_ids)
        orders = leads.mapped('order_ids').filtered(lambda o: o.state in ('draft', 'sent'))
        if not orders:
            raise UserError(_("Las oportunidades seleccionadas no tienen presupuestos en estado borrador o enviado."))

        partners = orders.mapped('partner_id')
        if not partners:
            raise UserError(_("Los presupuestos no tienen cliente asignado."))

        summary_lines = []
        for o in orders:
            lead_name = o.opportunity_id.name if o.opportunity_id else ''
            partner_name = o.partner_id.name if o.partner_id else ''
            summary_lines.append(
                '<li><b>%s</b> — %s € — %s <span style="color:#888;">(%s)</span></li>' % (
                    o.name, '{:,.2f}'.format(o.amount_total), partner_name, lead_name
                )
            )
        summary = '<ul>%s</ul>' % ''.join(summary_lines)

        res.update({
            'lead_ids': [(6, 0, leads.ids)],
            'order_ids': [(6, 0, orders.ids)],
            'partner_count': len(partners),
            'order_summary': summary,
        })
        return res

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if not self.template_id or not self.order_ids:
            return
        self.subject = _("Puertas de seguridad Roconsa | Presupuestos")
        self.body = _(
            '<p>Hola,</p>'
            '<p>Te envío los presupuestos solicitados, cualquier consulta estamos a disposición.</p>'
            '<p>¡Muchas gracias!</p>'
        )

    def action_send(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError(_("No hay presupuestos para enviar."))

        # Group orders by partner
        orders_by_partner = defaultdict(lambda: self.env['sale.order'])
        for order in self.order_ids:
            if order.partner_id:
                orders_by_partner[order.partner_id] |= order

        report = self.env.ref('sale.action_report_saleorder')
        all_order_names = ', '.join(self.order_ids.mapped('name'))

        for partner, orders in orders_by_partner.items():
            if not partner.email:
                raise UserError(_("El cliente %s no tiene dirección de correo.") % partner.name)

            # 1. Generate one PDF per order
            attachment_ids = []
            for order in orders:
                pdf_content, _fmt = report._render_qweb_pdf([order.id])
                pdf_b64 = base64.b64encode(pdf_content)
                att = self.env['ir.attachment'].create({
                    'name': '%s.pdf' % order.name,
                    'type': 'binary',
                    'datas': pdf_b64,
                    'res_model': 'sale.order',
                    'res_id': order.id,
                    'mimetype': 'application/pdf',
                })
                attachment_ids.append(att.id)

            # 2. Collect commercial material, deduplicate
            seen_material_ids = set()
            for order in orders:
                for mat_att in order.commercial_material_ids:
                    if mat_att.id not in seen_material_ids:
                        seen_material_ids.add(mat_att.id)
                        attachment_ids.append(mat_att.id)

            # 3. Personalize subject and body
            order_names = ', '.join(orders.mapped('name'))
            subject = self.subject or _('Presupuestos')
            if '{presupuestos}' in subject:
                subject = subject.replace('{presupuestos}', order_names)
            body = self.body or ''
            if '{cliente}' in str(body):
                body = body.replace('{cliente}', partner.name)

            # 4. Create and send mail
            mail_values = {
                'subject': subject,
                'body_html': body,
                'email_from': self.env.user.email_formatted
                              or self.env.company.email_formatted
                              or self.env.user.email,
                'email_to': partner.email,
                'recipient_ids': [(4, partner.id)],
                'attachment_ids': [(6, 0, attachment_ids)],
                'auto_delete': False,
            }
            mail = self.env['mail.mail'].sudo().create(mail_values)
            mail.send()

            # 5. Post note in chatter of each order
            for order in orders:
                order.message_post(
                    body=_(
                        "Correo masivo enviado a <b>%s</b> con los presupuestos: %s"
                    ) % (partner.name, order_names),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        # 6. Post note in chatter of each lead
        for lead in self.lead_ids:
            lead_orders = self.order_ids.filtered(lambda o: o.opportunity_id.id == lead.id)
            if lead_orders:
                order_names = ', '.join(lead_orders.mapped('name'))
                lead.message_post(
                    body=_(
                        "Correo masivo enviado con los presupuestos: %s"
                    ) % order_names,
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )

        return {'type': 'ir.actions.act_window_close'}
