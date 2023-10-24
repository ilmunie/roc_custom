from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

_ref_vat = {
    'al': 'ALJ91402501L',
    'ar': 'AR200-5536168-2 or 20055361682',
    'at': 'ATU12345675',
    'au': '83 914 571 673',
    'be': 'BE0477472701',
    'bg': 'BG1234567892',
    # Swiss by Yannick Vaucher @ Camptocamp
    'ch': 'CHE-123.456.788 TVA or CHE-123.456.788 MWST or CHE-123.456.788 IVA',
    'cl': 'CL76086428-5',
    'co': 'CO213123432-1 or CO213.123.432-1',
    'cy': 'CY10259033P',
    'cz': 'CZ12345679',
    'de': 'DE123456788',
    'dk': 'DK12345674',
    'do': 'DO1-01-85004-3 or 101850043',
    'ec': 'EC1792060346-001',
    'ee': 'EE123456780',
    'el': 'EL12345670',
    'es': 'ESA12345674',
    'fi': 'FI12345671',
    'fr': 'FR23334175221',
    'gb': 'GB123456782 or XI123456782',
    'gr': 'GR12345670',
    'hu': 'HU12345676',
    'hr': 'HR01234567896',  # Croatia, contributed by Milan Tribuson
    'ie': 'IE1234567FA',
    'in': "12AAAAA1234AAZA",
    'is': 'IS062199',
    'it': 'IT12345670017',
    'lt': 'LT123456715',
    'lu': 'LU12345613',
    'lv': 'LV41234567891',
    'mc': 'FR53000004605',
    'mt': 'MT12345634',
    'mx': 'MXGODE561231GR8 or GODE561231GR8',
    'nl': 'NL123456782B90',
    'no': 'NO123456785',
    'pe': '10XXXXXXXXY or 20XXXXXXXXY or 15XXXXXXXXY or 16XXXXXXXXY or 17XXXXXXXXY',
    'pl': 'PL1234567883',
    'pt': 'PT123456789',
    'ro': 'RO1234567897',
    'rs': 'RS101134702',
    'ru': 'RU123456789047',
    'se': 'SE123456789701',
    'si': 'SI12345679',
    'sk': 'SK2022749619',
    'sm': 'SM24165',
    # Levent Karakas @ Eska Yazilim A.S.
    'tr': 'TR1234567890 (VERGINO) or TR17291716060 (TCKIMLIKNO)',
    'xi': 'XI123456782',
}

class ResPartner(models.Model):
    _inherit = 'res.partner'

    phone = fields.Char(widget="phone")
    mobile = fields.Char(widget="mobile")
    professional = fields.Boolean(string="Profesional")

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []
        if name:
            args += ['|', ('email', 'ilike', name),'|', ('street', 'ilike', name), '|', ('phone', 'ilike', name), '|', ('mobile', 'ilike', name), '|', ('vat', 'ilike', name), ('name', 'ilike', name)]

            name = ''
        return super(ResPartner, self).name_search(name=name, args=args, operator=operator, limit=limit)

    @api.constrains('vat', 'country_id')
    def check_vat(self):
        # The context key 'no_vat_validation' allows you to store/set a VAT number without doing validations.
        # This is for API pushes from external platforms where you have no control over VAT numbers.
        if self.env.context.get('no_vat_validation'):
            return

        if self.env.context.get('company_id'):
            company = self.env['res.company'].browse(
                self.env.context['company_id'])
        else:
            company = self.env.company

        for partner in self:
            if not partner.company_id:
                if company.check_vat:
                    country = partner.commercial_partner_id.country_id
                    if partner.vat and self._run_vat_test(partner.vat, country, partner.is_company) is False:
                        partner_label = _("partner [%s]", partner.name)
                        msg = partner._build_vat_error_message(
                            country and country.code.lower() or None, partner.vat, partner_label)
                        raise ValidationError(msg)
            elif partner.company_id.check_vat:
                country = partner.commercial_partner_id.country_id
                if partner.vat and self._run_vat_test(partner.vat, country, partner.is_company) is False:
                    partner_label = _("partner [%s]", partner.name)
                    msg = partner._build_vat_error_message(
                        country and country.code.lower() or None, partner.vat, partner_label)
                    raise ValidationError(msg)

    @api.model
    def _build_vat_error_message(self, country_code, wrong_vat, record_label):
        if self.env.context.get('company_id'):
            company = self.env['res.company'].browse(
                self.env.context['company_id'])
        else:
            company = self.env.company

        expected_format = _ref_vat.get(
            country_code, "'CC##' (CC=Country Code, ##=VAT Number)")
        if company.check_vat:
            if company.vat_check_vies:
                return '\n' + _(
                    "The VAT number [%(wrong_vat)s] for %(record_label)s either failed the VIES VAT validation check or did not respect the expected format %(expected_format)s.",
                    wrong_vat=wrong_vat,
                    record_label=record_label,
                    expected_format=expected_format,
                )

            return '\n' + _(
                'The VAT number [%(wrong_vat)s] for %(record_label)s does not seem to be valid. \nNote: the expected format is %(expected_format)s',
                wrong_vat=wrong_vat,
                record_label=record_label,
                expected_format=expected_format,
            )