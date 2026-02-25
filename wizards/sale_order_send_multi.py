import base64
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrderSendMulti(models.TransientModel):
    _name = 'sale.order.send.multi'
    _description = 'Envío masivo de presupuestos'

    order_ids = fields.Many2many('sale.order', string="Presupuestos")
    partner_id = fields.Many2one('res.partner', string="Cliente", readonly=True)
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
            raise UserError(_("Debe seleccionar al menos un presupuesto."))
        orders = self.env['sale.order'].browse(active_ids)
        partners = orders.mapped('partner_id')
        if len(partners) > 1:
            names = ', '.join(partners.mapped('name'))
            raise UserError(_(
                "Los presupuestos seleccionados pertenecen a distintos clientes: %s. "
                "Solo se puede enviar a un mismo cliente."
            ) % names)
        partner = partners[0] if partners else False
        summary_lines = []
        for o in orders:
            summary_lines.append(
                '<li><b>%s</b> — %s €</li>' % (o.name, '{:,.2f}'.format(o.amount_total))
            )
        summary = '<ul>%s</ul>' % ''.join(summary_lines)
        res.update({
            'order_ids': [(6, 0, orders.ids)],
            'partner_id': partner.id if partner else False,
            'order_summary': summary,
        })
        return res

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if not self.template_id or not self.order_ids:
            return
        order_names = ', '.join(self.order_ids.mapped('name'))
        partner_name = self.partner_id.name or ''
        self.subject = _("Puertas de seguridad Roconsa | Presupuestos: %s") % order_names
        self.body = _(
            '<p>Hola %s,</p>'
            '<p>Te envío los presupuestos solicitados, cualquier consulta estamos a disposición.</p>'
            '<p>¡Muchas gracias!</p>'
        ) % partner_name

    def action_send(self):
        self.ensure_one()
        if not self.order_ids:
            raise UserError(_("No hay presupuestos para enviar."))

        partner = self.partner_id
        if not partner.email:
            raise UserError(_("El cliente %s no tiene dirección de correo.") % partner.name)

        # 1. Generate one PDF per sale.order
        report = self.env.ref('sale.action_report_saleorder')
        attachment_ids = []
        for order in self.order_ids:
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

        # 2. Collect commercial material, deduplicate by att.id
        seen_material_ids = set()
        for order in self.order_ids:
            for mat_att in order.commercial_material_ids:
                if mat_att.id not in seen_material_ids:
                    seen_material_ids.add(mat_att.id)
                    attachment_ids.append(mat_att.id)

        # 3. Create and send mail.mail
        mail_values = {
            'subject': self.subject or _('Presupuestos'),
            'body_html': self.body or '',
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

        # 4. Post note in chatter of each sale.order
        order_names = ', '.join(self.order_ids.mapped('name'))
        for order in self.order_ids:
            order.message_post(
                body=_(
                    "Correo masivo enviado a <b>%s</b> con los presupuestos: %s"
                ) % (partner.name, order_names),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

        return {'type': 'ir.actions.act_window_close'}
