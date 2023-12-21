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



class SupplierinfoImport(models.TransientModel):
    _name = "supplierinfo.import"
    _description = "Supplierinfo Import"

    file = fields.Binary(string='File', filename="filename")
    filename = fields.Char(string='Filename', size=256)
    state = fields.Selection([('draft','Draft'),('done','Done')], string='State', default='draft')
    message = fields.Html(string='Message', readonly=True)

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

    def _set_default_warn_msg(self):
        msg = _("La importación se ha completado correctamente.")
        return """
        <td height="45" align="left">
            <strong>
                <span style='font-size:10.0pt;font-family:Arial;color:green'>%s</span>
            </strong>
        </td>
        """ % msg

    def _set_default_error_msg(self, message):
        msg = _("Se completó la importación con errores.")
        return """
        <td height="45" align="left">
            <strong>
                <span style='font-size:10.0pt;font-family:Arial;color:red'>""" + msg + """</span>
            </strong>
            <br>
            <strong>
                <span style='font-size:10.0pt;font-family:Arial;color:black'>""" + message[:-2] + """</span>
            </strong>
        </td>
        """


    def get_supplier(self, sheet, curr_row):
        supplier = False
        mess = False
        error = False
        avoid_refresh = False
        name = str(self._read_cell(sheet, curr_row, 6) or '')
        vat = str(self._read_cell(sheet, curr_row, 8) or '')
        if not vat and not name:
            mess = '<span> FILA ' + str(curr_row) + ' | FALTA REFERENCIA PROVEEDOR<span/>'
            error = True
        if vat and not error:
            vat_partners = self.env['res.partner'].search([('vat', '=', vat)])
            for vat_partner in vat_partners:
                if vat_partner.name == name:
                    supplier = vat_partner.id
            if vat_partners and not supplier:
                supplier = vat_partner[0].id
                mess = '<span> FILA ' + str(curr_row) + ' | CIF no corresponde a nombre<span/>'
        if not supplier and not error:
            name_partners = self.env['res.partner'].search([('name', '=', name)])
            if not name_partners:
                mess = '<span> FILA ' + str(curr_row) + ' | PROVEEDOR CREADO<span/>'
                account_code = str(int(self._read_cell(sheet, curr_row, 1) or 0) or '')
                if not account_code:
                    mess = '<span> FILA ' + str(curr_row) + ' | ERROR CREACIÓN PROVEEDOR: FALTA COD CUENTA<span/>'
                    error = True
                else:
                    accounts = self.env['account.account'].search([('code', '=', account_code)])
                    if not accounts:
                        mess = '<span> FILA ' + str(curr_row) + ' | ERROR CREACIÓN PROVEEDOR: FALTA CUENTA<span/>'
                        error = True
                    else:
                        account_id = accounts[0].id
                        vals = {'name':name, 'vat': vat, 'property_account_payable_id': account_id }
                        avoid_refresh = True
                        supplier = self.env['res.partner'].create(vals).id
            else:
                mess = '<span> FILA ' + str(curr_row) + ' | CIF ACTUALIZADO PROVEEDOR<span/>'
                name_partners[0].vat = vat
                supplier = name_partners[0].id
        #ACTIALIZAR CUENTA
        if supplier and not avoid_refresh:
            partner = self.env['res.partner'].browse(supplier)
            account_code = str(int(self._read_cell(sheet, curr_row, 1) or 0) or '')
            if not account_code:
                mess = '<span> FILA ' + str(curr_row) + ' | ERROR FALTA COD CUENTA<span/>'
                error = True
            else:
                accounts = self.env['account.account'].search([('code', '=', account_code)])
                if not accounts:
                    mess = '<span> FILA ' + str(curr_row) + ' | ERROR FALTA CUENTA<span/>'
                    error = True
                else:
                    if partner[0].property_account_payable_id.id != accounts[0].id:
                        partner[0].property_account_payable_id = accounts[0].id
        return supplier, mess, error

    def get_product_lines(self, sheet, curr_row):
        lines = []
        mess = False
        error = False
        product_name = str(self._read_cell(sheet, curr_row, 7) or '')
        bi = float(str(self._read_cell(sheet, curr_row, 15) or 0))
        iva_21 = float(str(self._read_cell(sheet, curr_row, 16) or 0))
        iva_10 = float(str(self._read_cell(sheet, curr_row, 17) or 0))
        iva_5 = float(str(self._read_cell(sheet, curr_row, 18) or 0))
        if iva_21 > 0 and (iva_10 > 0 or iva_5 > 0):
            mess = f'<span>FILA {curr_row} | ERROR MULTIPLE IVA</span>'
            error = True
        if not error:
            irpf_15 = float(str(self._read_cell(sheet, curr_row, 21) or 0))
            irpf_19 = float(str(self._read_cell(sheet, curr_row, 22) or 0))
            irpf_7 = float(str(self._read_cell(sheet, curr_row, 23) or 0))
        if not error:
            if irpf_15 > 0 and (irpf_19 > 0 or irpf_7 > 0):
                mess = f'<span>FILA {curr_row} | ERROR MULTIPLE IRPF</span>'
                error = True
        if not error:
            req_eq = float(str(self._read_cell(sheet, curr_row, 19) or 0))
            matching_products = self.env['product.product'].search([('name','=',product_name)])
            if matching_products:
                product_id = matching_products[0].id
            else:
                account_code = str(int(self._read_cell(sheet, curr_row, 0) or 0))
                if not account_code:
                    mess = '<span> FILA ' + str(curr_row) + ' | ERROR CREACIÓN PRODUCTO: FALTA COD CUENTA<span/>'
                    error = True
                else:
                    accounts = self.env['account.account'].search([('code', '=', account_code)])
                    if not accounts:
                        mess = '<span> FILA ' + str(curr_row) + ' | ERROR CREACIÓN PRODUCTO: FALTA CUENTA<span/>'
                        error = True
                    else:
                        account_id = accounts[0].id
                        mess = '<span> FILA ' + str(curr_row) + ' | PRODUCTO CREADO<span/>'
                        product_id = self.env['product.product'].create({'name': product_name,'detailed_type': 'service', 'property_account_expense_id': account_id}).id
        if not error:
            tax_ids = []
            if iva_21 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_iva21_sc').id)
            if iva_10 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_iva10_sc').id)
            if iva_5 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_iva5_sc').id)
            if irpf_15 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_irpf15').id)
            if irpf_19 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_irpf19').id)
            if irpf_7 > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_irpf7').id)
            if req_eq > 0:
                tax_ids.append(self.env.ref('l10n_es.1_account_tax_template_p_req52').id)
            tax = [(6, 0, tax_ids)]
            lines.append((0, 0, {'product_id': product_id, 'quantity': 1, 'tax_ids': tax, 'price_unit': bi}))
        return lines, mess, error


    def read_file(self):
        product = self.env['product.product']
        message = []
        rows_with_payments = []
        #path = os.path.abspath(os.path.dirname(__file__))
        path = '/tmp/%s' % self.filename
        # ~ f = open(path, 'a')

        path = self.save_file(self.filename, self.file)
        import pdb

        if path:
            book = xlrd.open_workbook(path)
            invoices = []
            sheet = book.sheets()[0]
            for curr_row in range(1, sheet.nrows):
                vals = {}
                invoice_name = str(self._read_cell(sheet, curr_row, 1) or '')
                #if not invoice_name:
                #    message.append(f'<span>FILA {curr_row}: ERROR FALTA NUMERO FACTURA</span>')
                #    continue
                #else:
                #    if self.env['account.move'].search([('ref','=',invoice_name),('move_type','=','in_invoice')]):
                #        message.append(f'<span>FILA {curr_row}: FACTURA YA CREADA {invoice_name}</span>')
                #        continue
                #partner_id, mess, error = self.get_supplier(sheet, curr_row)
                #if mess:
                #    message.append(mess)
                #if error:
                #    continue
                #vals['partner_id'] = partner_id
                #product_lines, mess, error = self.get_product_lines(sheet, curr_row)
                #if mess:
                #    message.append(mess)
                #if error:
                #    continue
                #vals['invoice_line_ids'] = product_lines
                ##pdb.set_trace()
                #vals['invoice_date'] = self._read_cell(sheet, curr_row, 10) or False
                #vals['date'] = self._read_cell(sheet, curr_row, 10) or False
                #vals['invoice_date_due'] = self._read_cell(sheet, curr_row, 11) or False
                #vals['journal_id'] = 2
                #vals['ref'] = invoice_name
                #vals['move_type'] = 'in_invoice'
                date_payment = self._read_cell(sheet, curr_row, 2) or False
                if date_payment:
                    payment_method = self._read_cell(sheet, curr_row, 3)
                    journal_id = False
                    #pdb.set_trace()
                    if payment_method in ['EFECTIVO','METALICO']:
                        journal_id = 7
                    else:
                        cc = self._read_cell(sheet, curr_row, 4)
                        if cc:
                            rp_bank = self.env['res.partner.bank'].search([('acc_number','=',cc)])
                            if rp_bank:
                                journal_ids = self.env['account.journal'].search([('bank_account_id','=',rp_bank[0].id)])
                                if journal_ids:
                                    journal_id = journal_ids[0].id
                    if journal_id:
                        rows_with_payments.append(invoice_name)
                        vals['aux_payment_date'] = date_payment
                        vals['aux_journal_id'] = journal_id
                    else:
                        message.append(f'<span>FILA {str(curr_row)} : ERROR DIARIO PAGO</span>')
                        continue
                invoices.append(vals)
            error = False
            for mess in message:
                if 'ERROR' in mess:
                    error = True
            if not error:
                invs = self.env['account.move'].create(invoices)
                for inv in invs:
                    inv.action_post()
                    if inv.ref in rows_with_payments:
                        payment = self.env['account.payment'].create({
                            'date': inv.aux_payment_date,
                            'payment_type': 'outbound',
                            'partner_type': 'supplier',
                            'partner_id': inv.partner_id.id,
                            'amount': abs(inv.amount_total_signed),
                            'currency_id': self.env.user.company_id.currency_id.id,
                            'journal_id': inv.aux_journal_id.id,
                        })
                        payment.action_post()
                        receivable_line = payment.line_ids.filtered('debit')
                        inv.js_assign_outstanding_line(receivable_line.id)
                self.message = f'<span>{str(len(invoices))} FACTURAS CREADAS</span><br/>' + '<br/>'.join(message)
            else:
                self.message = '<br/>'.join(message)
            self.state = 'done'
            view = self.env.ref('roc_custom.view_supplierinfo_import')
            return {
                'name': _('Supplierinfo Import'),
                'res_model': 'supplierinfo.import',
                'type': 'ir.actions.act_window',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': self.id,}


