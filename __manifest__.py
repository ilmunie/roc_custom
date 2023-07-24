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
    ],
    'data': [
        'views/crm_lead.xml',
        'data/intrest_tag.xml',
        'security/ir.model.access.csv',
    ],
   
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
