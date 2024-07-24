# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2017 Eynes (http://www.eynes.com.ar)
#    All Rights Reserved. See AUTHORS for details.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import base64
import os
import xlrd
from odoo import _, exceptions, fields, models, api
from odoo.exceptions import UserError, ValidationError

class CrmLeadImport(models.TransientModel):
    _name = "crm.lead.import"
    _description = "Importacion Oportunidades"

    file = fields.Binary(string='Excel', filename="filename")
    filename = fields.Char(string='Nombre Archivo', size=256)
    state = fields.Selection([('draft', 'Nuevo'), ('done', 'Hecho')], string='State', default='draft')
    message = fields.Html(string='Mensaje', readonly=True)
    user_id = fields.Many2one('res.users', string="Comercial", required=True, default=lambda self: self.env.user.id)
    def save_file(self, name, value):
        path = '/tmp/%s' % name
        f = open(path, 'wb+')
        try:
            f.write(base64.decodebytes(value))
        finally:
            f.close()
        return path

    def _read_cell(self, sheet, row, cell):
        cell_type = sheet.cell_type(row, cell)
        cell_value = sheet.cell_value(row, cell)
        if cell_type in [1, 2]:  # 2: select, 1: text, 0: empty, 3: date
            return cell_value
        elif cell_type == 3:  # 3: date
            # Convertir el número de fecha en una fecha legible
            return xlrd.xldate.xldate_as_datetime(cell_value, 0)
        elif cell_type == 0:
            return None
        raise exceptions.UserError(_('Formato de archivo inválido'))

    def _set_default_warn_msg(self, message):
        return """
            <strong>
                <span style='font-size:10.0pt;font-family:Arial;color:green'>%s</span>
            </strong>
        """ % message

    def row_to_dict(self, sheet, curr_row):
        phone = self._read_cell(sheet, curr_row, 3) or ''
        if type(phone) == float:
            phone = str(int(phone))

        return {
            'row': curr_row,
            'partner_name': str(self._read_cell(sheet, curr_row, 0) or ''),
            'sector': str(self._read_cell(sheet, curr_row, 1) or ''),
            'contact_name': str(self._read_cell(sheet, curr_row, 2) or ''),
            'phone': phone.replace(' ', '').replace('-', '').replace(',', ''),
            'mail': str(self._read_cell(sheet, curr_row, 4) or ''),
            'last_contact': self._read_cell(sheet, curr_row, 5),
            'partner_intrest': str(self._read_cell(sheet, curr_row, 6) or ''),
            'address': str(self._read_cell(sheet, curr_row, 9) or ''),
            'loc': str(self._read_cell(sheet, curr_row, 11) or ''),
            'source': str(self._read_cell(sheet, curr_row, 10) or ''),
            'comments': str(self._read_cell(sheet, curr_row, 15) or ''),
        }

    def find_partner(self, vals):
        mess = []
        customer = False
        domain = []
        if vals['partner_name']:
            domain.append(('name', 'ilike', vals['partner_name']))
        if vals['phone']:
            if domain:
                domain.insert(0,'|')
            domain.append(('phone', 'ilike', vals['phone']))
            domain.insert(0, '|')
            domain.append(('mobile', 'ilike', vals['phone']))
        if vals['mail']:
            if domain:
                domain.insert(0, '|')
            domain.append(('email', 'ilike', vals['mail']))
        if len(domain) == 0:
            mess.append('<span> FILA ' + str(vals['row'] + 1) + ' | NO HAY DATOS DE CLIENTE<span/>')
        else:
            partners = self.env['res.partner'].search(domain)
            if len(partners)==0:
                no_data = False
                if not vals['partner_name'] and not vals['contact_name']:
                    mess.append('FILA ' + str(vals['row'] + 1) + ' | ERROR: CREACION CLIENTE: FALTA NOMBRE')
                    no_data = True
                if not vals['phone'] and not vals['mail']:
                    mess.append('FILA ' + str(vals['row'] + 1) + ' | ERROR: CREACION CLIENTE: FALTA MAIL - TEL')
                    no_data = True
                if not no_data:
                    mess.append('<span> FILA ' + str(vals['row'] + 1) + ' | NUEVO CLIENTE CREADO<span/>')
                    customer = self.env['res.partner'].create({
                        'name': vals['partner_name'] or vals['contact_name'],
                        'email': vals['mail'],
                        'phone': vals['phone'],
                        'street': vals['address'],
                        'city': vals['loc'],
                        'lang': 'es_ES',
                        'country_id': self.env.ref('base.es').id,
                        'mobile': vals['phone']}
                    ).id
            elif len(partners)==1:
                customer = partners[0].id
            elif len(partners)>1:
                mess.append('<span> FILA ' + str(vals['row'] + 1) + ' | VARIAS COINCIDENCIAS DE CLIENTE<span/>')
                customer = partners[0].id
        return customer, mess

    def get_workbook_sheet(self, book):
        """
        Busca tal que la primera celta sea SOCIEDAD. Excel con varias pages ocultas
        :param book:
        :return:
        """
        res = False
        for sheet in book.sheets():
            if str(self._read_cell(sheet, 0, 0) or '') != 'SOCIEDAD':
                continue
            else:
                res = sheet
        return res

    def customer_update(self, customer_id, vals):
        """
        Updates profesional field in partner and adds tags
        """
        partner = self.env['res.partner'].browse(customer_id)
        if not partner.professional:
            partner.professional = True
        if vals['sector']:
            tags = self.env['res.partner.category'].search([('name', '=', vals['sector'])])
            if tags and tags[0].id not in partner.category_id.mapped('id'):
                partner.category_id = [(4, tags[0].mapped('id'))]
        return

    def get_final_opp_vals(self, vals, customer_id):
        partner = self.env['res.partner'].browse(customer_id)
        team = self.env['crm.team'].search([('name', '=', 'Puerta Fria')])
        if not team:
            raise ValidationError('Cree un equipo de ventas con nombre Puerta Fria')
        source = self.env['utm.source'].search([('name', '=', 'Profesional Puerta Fria')])
        if not source:
            raise ValidationError('Cree un origen de oportunidad con nombre Profesional Puerta Fria')
        medium = self.env['utm.medium'].search([('name', '=', 'Profesional Puerta Fria')])
        if not medium:
            raise ValidationError('Cree un medio de oportunidad con nombre Profesional Puerta Fria')
        vals = {
            'name': 'PF: ' + partner.name,
            'partner_id': partner.id,
            'email_from': vals['mail'] or partner.email,
            'phone': vals['phone'] or partner.phone,
            'mobile': vals['phone'] or partner.mobile,
            'type': 'opportunity',
            'priority': False,
            'company_concern': False,
            'lang_id': self.env.ref('base.lang_es').id,
            'tag_ids': False,
            'team_id': team[0].id,
            'user_id': self.user_id.id,
            'description': vals['comments'],
            'contact_name': (vals['contact_name'] or '') or (vals['partner_name'] or '') or partner.name,
            'street': vals['address'] or partner.street or '',
            'city': vals['loc'] or partner.city,
            'country_id': partner.country_id.id if partner.country_id else self.env.ref('base.es').id,
            'source_id': source[0].id,
            'medium_id': medium[0].id,
        }
        return vals
    def read_file(self):
        message = []
        opp_to_create = []
        error = False
        path = self.save_file(self.filename, self.file)
        if path:
            book = xlrd.open_workbook(path)
            sheet = self.get_workbook_sheet(book)
            for curr_row in range(1, sheet.nrows):
                vals = self.row_to_dict(sheet, curr_row)
                customer_id, mess = self.find_partner(vals)
                message.extend(mess)
                if customer_id:
                    self.customer_update(customer_id, vals)
                    opp_to_create.append(self.get_final_opp_vals(vals, customer_id))
            for mess in message:
                if 'ERROR' in mess:
                    error = True
                    raise UserError('  -  '.join([mess for mess in message if 'ERROR' in mess]))
            if not error:
                opp = self.env['crm.lead'].create(opp_to_create)
                ok_mess = self._set_default_warn_msg(str(len(opp)) + " OPORTUNIDADES CREADAS")
                #import pdb;pdb.set_trace()
                ok_mess = ok_mess + '<br/>' + '<br/>'.join(message)
                self.message = ok_mess
            self.state = 'done'
            view = self.env.ref('roc_custom.crm_lead_import_import_view')
            return {
                'name': 'Importacion Oportunidades',
                'res_model': 'crm.lead.import',
                'type': 'ir.actions.act_window',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': self.id}


