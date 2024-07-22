from odoo import fields, models


class PosCloseSession(models.TransientModel):
    _name = 'pos.close.session'

    special_date = fields.Date(string="Fecha")
    def action_done(self):
        pos_sess = self.env['pos.session'].browse(self._context.get('active_ids', ['pos.session']))
        for ses in pos_sess:
            ses.with_context(min_close_date=self.special_date).custom_close_session()
        return
            
