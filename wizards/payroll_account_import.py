# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2017 Eynes (http://www.eynes.com.ar)
#    All Rights Reserved. See AUTuitHORS for details.
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
import json
import calendar

import xlrd
from odoo import _, exceptions, fields, models, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta

#asiento de anticiipo: cuando se le da: 460000000 al debe y al haber la del banco/efectivo

conversion_dict = {
    'TOTAL DEVENGOS': ['debe','640000000'], #gasto con aaa
    '(00008) 050 DCTO ESP': ['haber','640000000'],
    '(00008) 400 DTO.ESPEC': ['haber','640000000'],
    '(00008) 838 DTO.C.COM': ['haber','476000000'],
    '(00008) 060 DIF. NETO': ['haber','465000000'],
    '(00008) 610 EMB.SALAR.': ['haber','465000000'],
    '(00008) 840 DTO.ACC.': ['haber', '476000000'],
    '(00008) 862 RETEN.IRPF': ['haber', '475100001'],
    '(00008) 762 RETEN.IRPF': ['haber', '475100001'],
    '(00008) 023 DC.MULTAS': ['haber', '659000001'],
    '(00008) 863 RET.V.ESP.': ['haber', '475100001'],
    '(00008) 021 ANTICIPO': ['haber', '460000000'],
    'TOTAL LIQUIDO': ['haber', '465000000'],
    '(00008) 839 DTO.H.EXT': ['haber', '476000000'],
    'TOTAL COSTE S.S.': ['haber', '476000000'],
    #'TOTAL COSTE S.S.': ['debe', '642000000'], #gasto con aaa
}

first_payment = {
    'debe_concepts': ['TOTAL LIQUIDO'],
    'haber_account': '572000001',
}
# total liquido (debe: 465000000) vs banco al haber

ss_payement = {
    'debe_concepts': ['TOTAL COSTE S.S.'],
    'haber_account': '572000005',
}

# ultimo dia del mes siguiente pago de  TOTAL COSTE S.S.
# 'TOTAL COSTE S.S.' va de la 476000000 (debe) al haber del banco con la que se pago

tax_dict = {
    'payment_dates': ['20/04/2023','20/07/2023','20/10/2023','20/01/2024'],
    'debe_concepts': ['(00008) 862 RETEN.IRPF','(00008) 863 RET.V.ESP.'],
    'haber_account': '572000005',
}

analytic_tags = ['640','642']

class PayrollAnalyticDistributor(models.TransientModel):
    _name = "payroll.analytic.distributor"
    _description = "Payroll Importer Analytic Distributor"

    analytic_tag_id = fields.Many2one('account.analytic.tag')
    payroll_key = fields.Char()
    html_payroll_reference = fields.Html()
    wiz_id = fields.Many2one('payroll.account.import')

    def apply_same_dist(self):
        self.ensure_one()
        vals = self.wiz_id.distributor_ids
        vals_to_write = vals.filtered(lambda x: x.payroll_key.split("||")[0] == self.payroll_key.split("||")[0])
        for val in vals_to_write:
            val.analytic_tag_id = self.analytic_tag_id.id if self.analytic_tag_id else False
        view = self.env.ref('roc_custom.view_payroll_import')
        return {
                'name': _('Importación de Nóminas'),
                'res_model': 'payroll.account.import',
                'type': 'ir.actions.act_window',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': self.wiz_id.id, }

class PayrollAccountImport(models.TransientModel):
    _name = "payroll.account.import"
    _description = "Payroll Account Import"

    distributor_ids = fields.One2many('payroll.analytic.distributor','wiz_id')

    file_attachments = fields.Many2many(
        'ir.attachment', string='File Attachments',
        help='Attach one or more files to this record.'
    )
    result = fields.Text()
    state = fields.Selection([('draft','Draft'),('done','Done')], string='State', default='draft')
    message = fields.Html(string='Message', readonly=True)


    def generate_account_move(self):
        vals_to_create = []
        first_payment_dict = {}
        ss_payment_dict = {}
        tax_payment_dict = {}
        result = json.loads(self.result)
        journal_id = self.env['account.journal'].search([('name','=','Nominas')])
        payment_journal_id = self.env['account.journal'].search(['|',('name','=','Banco CAIXA  6128 (Impuestos)'),('name','=','Banco CAIXA 6128 (Impuestos)')])
        if not journal_id:
            raise ValidationError('No se encontró el diario Nominas')
        if not payment_journal_id:
            raise ValidationError('No se encontró el diario de pagos Banco CAIXA 6128 (Impuestos)')
        for key, values in result.items():
            employee_name = key.split("||")[0]
            date = datetime.strptime(values[0]['date'], '%Y-%m-%d %H:%M:%S')
            ref = "Nominas " + date.strftime('%m/%Y') + ' ' + employee_name
            date_key = "Nominas " + date.strftime('%m/%Y')
            tax_payemnt_date, trim = self.get_tax_payment_date_info(date)
            trim = "PAGO RETENCIONES " + trim
            if date_key not in first_payment_dict.keys():
                first_payment_dict[date_key] = []
            if date_key not in ss_payment_dict.keys():
                ss_payment_dict[date_key] = []
            if trim not in tax_payment_dict.keys():
                tax_payment_dict[trim] = []
            lines = []
            for line in values:
                if line['amount'] < 0:
                    line['side'] = 'debe' if line['side'] == 'haber' else 'haber'
                distribution = any(line['account_code'].startswith(tag) for tag in analytic_tags)
                lines.append((0,0, {
                        'account_id': self.env['account.account'].search([('code','=', line['account_code'])])[0].id,
                        #'partner_id':,
                        'name': ref + " | " + line['key'],
                        'analytic_tag_ids': [(6, 0, self.distributor_ids.filtered(lambda x: x.payroll_key == key)[0].analytic_tag_id.mapped('id'))] if distribution else False,
                        'debit': abs(line['amount']) if line['side'] == 'debe' else 0,
                        'credit': abs(line['amount']) if line['side'] == 'haber' else 0,
                }))
                if line['key'] in first_payment['debe_concepts']:
                    first_payment_dict[date_key].append((0, 0, {
                        'date': date,
                        'account_id': self.env['account.account'].search([('code', '=', line['account_code'])])[0].id,
                        # 'partner_id':,
                        'name': "PAGO " + ref + " | " + line['key'],
                        # 'analytic_tag_ids':
                        'debit': abs(line['amount']) if line['amount'] > 0 else 0,
                        'credit':  0 if line['amount'] > 0 else abs(line['amount']),
                    }))
                if line['key'] in ss_payement['debe_concepts']:
                    ss_payment_dict[date_key].append((0, 0, {
                        'date': date,
                        'account_id': self.env['account.account'].search([('code', '=', line['account_code'])])[
                            0].id,
                        # 'partner_id':,
                        'name': "PAGO " + ref + " | " + line['key'],
                        # 'analytic_tag_ids':
                        'debit': abs(line['amount']) if line['amount'] > 0 else 0,
                        'credit': 0 if line['amount'] > 0 else abs(line['amount']),
                    }))
                if line['key'] in tax_dict['debe_concepts']:
                    #import pdb;
                    #pdb.set_trace()
                    tax_payment_dict[trim].append((0, 0, {
                        'date': tax_payemnt_date,
                        'account_id': self.env['account.account'].search([('code', '=', line['account_code'])])[
                            0].id,
                        # 'partner_id':,
                        'name': "PAGO " + ref + " | " + line['key'],
                        # 'analytic_tag_ids':
                        'debit': abs(line['amount']) if line['amount'] > 0 else 0,
                        'credit':  0 if line['amount'] > 0 else abs(line['amount']),
                    }))
            vals_to_create.append({
                'ref': ref,
                'date': date,
                'journal_id': journal_id[0].id,
                'line_ids': lines,
                })
        created_vals = []
        created_vals.extend(self.env['account.move'].create(vals_to_create))

        for key, values in first_payment_dict.items():
            amount = sum(line[2].get('debit', 0) - line[2].get('credit', 0) for line in values)
            first_payment_dict[key].append((0, 0, {
                    'account_id': self.env['account.account'].search([('code', '=', first_payment['haber_account'])])[
                        0].id,
                    # 'partner_id':,
                    'name': key + " | PAGO " + ','.join(first_payment['debe_concepts']),
                    # 'analytic_tag_ids':
                    'debit': 0 if amount > 0 else abs(amount),
                    'credit': abs(amount) if amount > 0 else 0,
                }))
            self.env['account.move'].create({
                'ref': key + " | PAGO EMPLEADO",
                'date': values[0][2]['date'],
                'journal_id': payment_journal_id[0].id,
                'line_ids': first_payment_dict[key],
            })

        for key, values in ss_payment_dict.items():
            amount = sum(line[2].get('debit', 0) - line[2].get('credit', 0) for line in values)
            ss_payment_dict[key].append((0, 0, {
                    'account_id': self.env['account.account'].search([('code', '=', ss_payement['haber_account'])])[
                        0].id,
                    # 'partner_id':,
                    'name': key + " | PAGO " + ','.join(ss_payement['debe_concepts']),
                    # 'analytic_tag_ids':
                    'debit': 0 if amount > 0 else abs(amount),
                    'credit': abs(amount) if amount > 0 else 0,
                }))
            date = values[0][2]['date']
            month = date.month + 2
            month = month - 12 if month > 12 else month
            first_day_of_next_month = datetime(date.year, month, 1)
            last_day_of_next_month = first_day_of_next_month - timedelta(days=1)
            self.env['account.move'].create({
                'ref': key + " | PAGO CARGAS SOCIALES",
                'date': last_day_of_next_month,
                'journal_id': payment_journal_id[0].id,
                'line_ids': ss_payment_dict[key],
            })
        line = False
        #import pdb;pdb.set_trace()
        for key, values in tax_payment_dict.items():
            date_arch = values[0][2]['date']
            closest_or_next_payment_date, trim = self.get_tax_payment_date_info(date_arch)
            amount = sum(line[2].get('debit', 0) - line[2].get('credit', 0) for line in values)
            trim_existing_move = self.env['account.move'].search([('ref', '=', key)])
            if trim_existing_move and trim_existing_move[0].line_ids.filtered(lambda x: x.account_id.name == 'CAIXA 6128'):
                if trim_existing_move[0].state != 'draft':
                    trim_existing_move[0].button_draft()
                line = trim_existing_move[0].line_ids.filtered(lambda x: x.account_id.code == tax_dict['haber_account'])[0]
                line_amount = -line.debit if line.debit else line.credit
                line_amount += amount
                tax_payment_dict[key].append((1, line.id, {
                    'credit': abs(line_amount) if line_amount > 0 else 0,
                    'debit': 0 if line_amount > 0 else abs(line_amount)}))
            else:
                tax_payment_dict[key].append((0, 0, {
                        'date': closest_or_next_payment_date,
                        'account_id': self.env['account.account'].search([('code', '=', tax_dict['haber_account'])])[
                            0].id,
                        # 'partner_id':,
                        'name': key + " | PAGO " + ','.join(tax_dict['debe_concepts']),
                        # 'analytic_tag_ids':
                        'debit': 0 if amount > 0 else abs(amount),
                        'credit': abs(amount) if amount > 0 else 0,
                    }))
        #import pdb;pdb.set_trace()
        for key, lines in tax_payment_dict.items():
            trim_existing_move = self.env['account.move'].search([('ref','=', key)])
            if trim_existing_move:
                if trim_existing_move[0].state != 'draft':
                    trim_existing_move[0].button_draft()
                trim_existing_move[0].write({'line_ids': lines})
            else:
                self.env['account.move'].create({
                    'ref': key,
                    'date': lines[0][2]['date'],
                    'journal_id': payment_journal_id[0].id,
                    'line_ids': tax_payment_dict[key],
                })
        return False

    def get_tax_payment_date_info(self, given_date):
        if isinstance(given_date, str):
            given_date = datetime.strptime(given_date, '%d/%m/%Y')
        for payment_date in tax_dict['payment_dates']:
            payment_date_obj = datetime.strptime(payment_date, '%d/%m/%Y')
            #import pdb;pdb.set_trace()
            # Check if the payment date is after or equal to the given date
            if payment_date_obj >= given_date:
                # Determine the trimester
                trimester = self.get_trimester(payment_date_obj.month)
                return payment_date_obj, trimester

    def get_trimester(self, month):
        if month == 4:
            return 'PRIMER TRIMESTRE'
        elif month == 7:
            return 'SEGUNDO TRIMESTRE'
        elif month == 10:
            return 'TERCER TRIMESTRE'
        elif month == 1:
            return 'CUARTO TRIMESTRE'
    def process_files(self):
        message_dict = {}
        result = {}
        distributor_vals = []
        for file in self.file_attachments:
            path = self.save_file(file.name, file.datas)
            #import pdb;pdb.set_trace()
            if path:
                book = xlrd.open_workbook(path)
                sheet = book.sheets()[0]
                date_cell = self._read_cell(sheet, 2, 6)
                date_index = date_cell.find(':') if date_cell else -1
                message_dict[file.name] = []
                if date_index != -1:
                    date = datetime.strptime(date_cell[date_index + 1:].strip(), "%d/%m/%Y")
                else:
                    message_dict[file.name] = [f'ERROR | ARCHIVO {file.name} | Fecha de las nóminas no encontrada']
                    continue
                for curr_col in range(2, sheet.ncols):
                    employee_text = ''
                    name = self._read_cell(sheet, 8, curr_col)
                    last_name = self._read_cell(sheet, 9, curr_col)
                    second_last_name = self._read_cell(sheet, 10, curr_col)
                    employee_text += name + ' ' if name else employee_text
                    employee_text += last_name + ' ' if last_name else employee_text
                    employee_text += second_last_name + ' ' if second_last_name else employee_text
                    if not employee_text:
                        message_dict[file.name].extend((f'ERROR Columna {str(curr_col)} | Falta nombre empleado'))
                    else:
                        result[employee_text + "||" + file.name] = []
                    for curr_row in range(12, sheet.nrows):
                        row_name = self._read_cell(sheet, curr_row,0).strip()
                        if row_name in conversion_dict.keys():
                            value = self._read_cell(sheet, curr_row, curr_col)
                            if value:
                                config = conversion_dict.get(row_name, False)
                                if config:
                                    vals = {
                                        'date': date,
                                        'amount': value,
                                        'key': row_name,
                                        'side': config[0],
                                        'account_code': config[1],
                                        'analytic_tag':False,
                                        'file': file.name,
                                    }
                                    result[employee_text + "||" + file.name].append(vals)
                                    #manual approach of special assigment
                                    if row_name == 'TOTAL COSTE S.S.':
                                        vals = {
                                            'date': date,
                                            'amount': value,
                                            'key': row_name + "||",
                                            'side': 'debe',
                                            'account_code': '642000000',
                                            'analytic_tag': False,
                                            'file': file.name,
                                        }
                                        result[employee_text + "||" + file.name].append(vals)


            #FUNCTION TO CHECK THAT ALL THE KEYS IN THE conversion_dict ARE PRESENT IN THE RESULT. CHECK THAT FOR EACH EMPLOYEE_KEY.
            # IN THE ERRORS DICT Y HAVE TO APPEND A LINE REPORTING FOR THAT EMPLOYEE WITH KEYS OF HAVE NOT BEEN FOUND
            #
        distributor_vals = []
        for employee_text, values in result.items():
                debe_sum = round(sum(val['amount'] for val in values if val['side'] == 'debe'),2)
                haber_sum = round(sum(val['amount'] for val in values if val['side'] == 'haber'),2)
                employee_name = employee_text.split("||")[0]
                ref = "Nomina " + values[0]['date'].strftime('%m/%Y') + ' ' + employee_name
                analytic_tag = self.env['account.analytic.tag'].search([('name', 'ilike', employee_name)])

                distributor_val = {'payroll_key': employee_text,
                                   'wiz_id': self.id,
                                   'html_payroll_reference': ref,
                                   'analytic_tag_id':  analytic_tag[0].id if analytic_tag else False
                                   }
                if debe_sum != haber_sum:
                    distributor_val['html_payroll_reference'] += f"<br/><span style='color:red;'>ERROR | El asiento no balancea. 'Debe' ({debe_sum}) 'Haber' ({haber_sum})</span>"

                distributor_vals.append(distributor_val)
        self.env['payroll.analytic.distributor'].create(distributor_vals)
        msg = []
        #for key, value in message_dict.items():
        #        msg.append("<strong>ARCHIVO |" + key + '</strong>' or '')
        #        msg.extend(value)
        #        msg.append('<br/><br/>')
        #self.message = '<br/>'.join(msg)
        self.state = 'done'
        self.result = json.dumps(result, default=str)
        view = self.env.ref('roc_custom.view_payroll_import')
        return {
                'name': _('Importación de Nóminas'),
                'res_model': 'payroll.account.import',
                'type': 'ir.actions.act_window',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': self.id, }


    #file = fields.Binary(string='File', filename="filename")
    #filename = fields.Char(string='Filename', size=256)


    def save_file(self, name, value):

        #path = os.path.abspath(os.path.dirname(__file__))
        path = '/tmp/%s' % name
        f = open(path, 'wb+')
        try:
            f.write(base64.decodebytes(value))
        finally:
            f.close()

        return path

    def _read_cell(self, sheet, row, cell):
        #import pdb;pdb.set_trace()
        cell_type = sheet.cell_type(row, cell)
        cell_value = sheet.cell_value(row, cell)

        if cell_type in [1, 2]:  # 2: select, 1: text, 0: empty, 3: date
            if cell_type == '1':
                return cell_value.strip()
            else:
                return  cell_value
        elif cell_type == 3:  # 3: date
            # Convertir el número de fecha en una fecha legible
            return xlrd.xldate.xldate_as_datetime(cell_value, 0)
        elif cell_type == 0:
            return None

        raise exceptions.UserError(_('Formato de archivo inválido'))






