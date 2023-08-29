import base64
from odoo import _, api, fields, models, tools, Command
from odoo.exceptions import UserError
import json

class MailTemplateExtraReport(models.Model):
    _name = 'mail.template.extra.report'

    template_id = fields.Many2one('mail.template')
    field_id = fields.Many2one('ir.model.fields')
    @api.depends('template_id.model_id')
    def get_fields_domain(self):
        for record in self:
            ids = self.env['ir.model.fields'].search([('relation','!=',False),('model_id','=',record.template_id.model_id.id)]).mapped('id')
            record.field_domain_ids = json.dumps([('id','in',ids)])

    field_domain_ids = fields.Char(compute=get_fields_domain, store=True)
    @api.depends('field_id')
    def get_template_domain(self):
        for record in self:
            model = record.field_id.relation if record.field_id else False
            if model:
                model_id = self.env['ir.model'].search([('model','=',model)]).id
            else:
                model_id = False
            ids = self.env['mail.template'].search([('model_id','=',model_id)]).mapped('id')
            record.template_domain_ids = json.dumps([('id','in',ids)])

    template_domain_ids = fields.Char(compute=get_template_domain, store=True)
    report_template_id = fields.Many2one('mail.template')

class MailTemplate(models.Model):
    _inherit = "mail.template"

    other_model_reports = fields.Boolean()
    extra_report_template_ids = fields.One2many('mail.template.extra.report','template_id')

    def generate_email(self, res_ids, fields):
        results = super(MailTemplate, self).generate_email(res_ids, fields)
        #import pdb;pdb.set_trace()
        if self.other_model_reports and self.extra_report_template_ids:
            for lang, (template, template_res_ids) in self._classify_per_lang(res_ids).items():
                for res_id in template_res_ids:
                    attachments = []
                    for extra_rep_template in self.extra_report_template_ids:
                        res_field = extra_rep_template.field_id.name
                        rec = self.env[template.model_id.model].browse(res_id)
                        obj_val = rec[res_field]
                        extra_tem = extra_rep_template.report_template_id
                        for extra_lang, (extra_template, extra_template_res_ids) in extra_tem._classify_per_lang(obj_val.mapped('id')).items():
                            for extra_res_id in extra_template_res_ids:
                                report_name = extra_template._render_field('report_name', [extra_res_id])[extra_res_id]
                                report = extra_template.report_template
                                report_service = report.report_name
                                if report.report_type in ['qweb-html', 'qweb-pdf']:
                                    result, format = report._render_qweb_pdf([extra_res_id])
                                else:
                                    res = report._render([extra_res_id])
                                    if not res:
                                        raise UserError(_('Unsupported report type %s found.', report.report_type))
                                    result, format = res
                                result = base64.b64encode(result)
                                if not report_name:
                                    report_name = 'report.' + report_service
                                ext = "." + format
                                if not report_name.endswith(ext):
                                    report_name += ext
                                attachments.append((report_name, result))
                    if 'attachments' not in results[res_id]:
                        results[res_id]['attachments'] = []
                    results[res_id]['attachments'].extend(attachments)
        return results




