# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _

class IntrestTag(models.Model):
    _name = 'intrest.tag'

    name = fields.Char()


class LeadLostReason(models.Model):
    _name = "lead.lost.reason"
    _description = 'Lead Lost Reason'

    name = fields.Char('Description', required=True, translate=True)

