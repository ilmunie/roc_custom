# -*- coding: utf-8 -*-
{
    'name': 'roc_custom',
    'version': '1.0',
    'category': 'Custom',
    'sequence': 15,
    'summary': 'Odoo v15 module with custom features for roc project',
    'description': "",
    'website': '',
    'depends': [
        'crm',
        'roc_crm',
        'web_widget_open_tab',
        'web_m2x_options',
    ],
    'data': [
        'wizards/lost_reason.xml',
        'wizards/crm_convert_opp_wizard.xml',
        'views/crm_lead.xml',
        'views/crm_complementary_models_views.xml',
        'data/intrest_tag.xml',
        'security/ir.model.access.csv',
    ],
    "assets": {
        "web.assets_backend": ["roc_custom/static/src/js/widget.js"],
        "web.assets_qweb": ["roc_custom/static/src/xml/template.xml"],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
