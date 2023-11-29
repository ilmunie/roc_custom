# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _

class CrmStage(models.Model):
    _inherit = 'crm.stage'

    active = fields.Boolean(default=True)

class CrmTag(models.Model):
    _inherit = 'crm.tag'
    _order = 'sequence'

    closer_follow = fields.Boolean(string="Seguimiento especial")
    sequence = fields.Integer(string="Orden")



class IntrestTag(models.Model):
    _name = 'intrest.tag'

    name = fields.Char()


class LeadLostReason(models.Model):
    _name = "lead.lost.reason"
    _description = 'Lead Lost Reason'

    name = fields.Char('Description', required=True, translate=True)


class CrmStageChange(models.Model):
    _name = "crm.stage.change"

    date = fields.Datetime()
    stage_id = fields.Many2one('crm.stage')
    opportunity_id = fields.Many2one('crm.lead')


class CrmLeadStageChange(models.Model):
    _name = "crm.lead.stage.change"

    date = fields.Datetime()
    lead_stage_id = fields.Many2one('crm.lead.stage')
    lead_id = fields.Many2one('crm.lead')

class CrmLeadStage(models.Model):
    _name = "crm.lead.stage"

    name = fields.Char(string="Name", required=True)
    sequence = fields.Integer(string="Sequence")

class CrmWorkType(models.Model):
    _name = 'crm.work.type'
    _description = 'Tipo de obra'

    name = fields.Char(
        string="Tipo de obra",
    )