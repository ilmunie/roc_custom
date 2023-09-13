from odoo import api, fields, models, SUPERUSER_ID, _
from dateutil.relativedelta import relativedelta



class ChangeDateDueWiz(models.TransientModel):
    _name = 'change.date.due.wiz'
    @api.model
    def default_get(self, fields):

        """ Allow support of active_id / active_model instead of jut default_lead_id
        to ease window action definitions, and be backward compatible. """
        result = super(ChangeDateDueWiz, self).default_get(fields)

        if not result.get('move_id') and self.env.context.get('active_id'):
            result['move_id'] = self.env.context.get('active_id')
        return result

    move_id = fields.Many2one(
        'account.move')
    date_due = fields.Date(related='move_id.invoice_date_due', readonly=False, force_save=True)

    def action_done(self):
        return
            
