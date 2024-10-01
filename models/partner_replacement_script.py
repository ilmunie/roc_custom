
from odoo import fields, models, api


class RespPartner(models.Model):
    _inherit = "res.partner"

    def replace_partner(self):
        partner_to_replace = self.env['res.partner'].browse(self._context.get('active_ids', []))
        wiz_line_vals = []
        for partner in partner_to_replace:
            wiz_line_vals.append((0, 0, {'old_partner_id': partner.id}))
        wiz_id = self.env['partner.replacement.wiz'].create({'line_ids': wiz_line_vals})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'partner.replacement.wiz',
            'res_id': wiz_id.id,
            'view_mode': 'form',
            'target': 'new',
        }


class PartnerReplacementWiz(models.Model):
    _name = "partner.replacement.wiz"

    line_ids = fields.One2many('partner.replacement.wiz.line', 'wiz_id')

    def action_done(self):
        fields_to_update = self.env['ir.model.fields'].search([('store', '=', True),
                                                               ('model', 'not ilike', 'hr_employee_base'),
                                                               ('model', 'not ilike', 'purchase_bill_union'),
                                                               ('model', 'not ilike', 'mail_followers'),
                                                               ('model', 'not ilike', 'account_aged'),
                                                               ('model', 'not ilike', 'report'),
                                                               ('relation', '=', 'res.partner'),
                                                               ('ttype', '=', 'many2one'),
                                                               ('model_id.transient', '=', False)])
        for line in self.line_ids.filtered(lambda x: x.old_partner_id and x.new_partner_id):
            for field_to_update in fields_to_update:
                    query = f"""
                            UPDATE {field_to_update.model.replace('.', '_')} 
                            SET {field_to_update.name} = %s
                            WHERE {field_to_update.name} = %s
                        """
                    self.env.cr.execute(query, (line.new_partner_id.id, line.old_partner_id.id))
        self.env.cr.commit()
        return False

class PartnerReplacementWizLine(models.Model):
    _name = "partner.replacement.wiz.line"

    wiz_id = fields.Many2one('partner.replacement.wiz')
    old_partner_id = fields.Many2one('res.partner')
    new_partner_id = fields.Many2one('res.partner')