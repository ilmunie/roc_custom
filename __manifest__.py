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
        'calendar',
        'web',
        'roc_sol',
        'account',
        'helpdesk',
        'hr',
        'sale',
        'sale_crm',
        'validation_builder',
        'fleet',
        'stock',
        'sale_stock',
        'crm_enterprise',
        'purchase_stock',
        'web_group_expand',
        'web_widget_open_tab',
        'web_m2x_options',
        'web_domain_field',
        'activity_automation',
        'mrp',
        'point_of_sale',
        'entrivis_kanban_many2many_tags',
        'web_tree_many2one_clickable',
        'stock_available_unreserved',
    ],
    'data': [
        'data/email_template_requeriment.xml',
        'security/groups.xml',
        'data/res_partner.xml',
        'data/lead_stage_data.xml',
        'data/helpdesk.xml',
        'data/technical_job_tag.xml',
        'data/validation_builder_data.xml',
        'data/ir_cron_data.xml',
        'wizards/change_date_due_wiz.xml',
        'wizards/change_aml_tax_view.xml',
        'wizards/po_alternative_additional_product_assistant_views.xml',
        'wizards/mrp_alternative_product_assistant_views.xml',
        'wizards/crm_convert_opp_wizard.xml',
        'wizards/modify_tags_masive.xml',
        'wizards/pos_close_session_view.xml',
        'wizards/payroll_account_import_view.xml',
        'wizards/sale_purchase_order_wizard_view.xml',
        'wizards/crm_lead_import_view.xml',
        'wizards/generate_sale_quotation_wizard.xml',
        'wizards/supplierinfo_import_view.xml',
        'views/ir_sequence.xml',
        'views/crm_tag_views.xml',
        'views/hr_views.xml',
        'views/report_stock_forecasted.xml',
        #'views/helpdesk_views.xml',
        'views/purchase_order_report.xml',
        'views/crm_lead_form_view.xml',
        'views/crm_lead_stage_views.xml',
        'views/sales_complementary_models.xml',
        'views/stock_picking.xml',
        'views/account_journal_view.xml',
        'views/account_move.xml',
        'views/invoice_report.xml',
        'views/stock_move.xml',
        'views/stock_move_line.xml',
        'views/stock_quant.xml',
        'views/mail_template_view.xml',
        'views/crm_lead.xml',
        'views/purchase_order.xml',
        'views/sale_order.xml',
        'views/pos_order_views.xml',
        'wizards/technical_job_quick_create_view.xml',
        'wizards/massive_pos_billing_view.xml',
        'views/res_partner.xml',
        'views/product_product_views.xml',
        'views/mrp_production.xml',
        'views/crm_complementary_models_views.xml',
        'views/sale_order_template_views.xml',
        'views/technical_job_views.xml',
        'views/technical_job_assistant_view.xml',
        'views/technical_job_note_assistant_views.xml',
        'views/technical_job_billing_assistant_views.xml',
        'views/technical_job_time_register_views.xml',
        'views/combo_variant_views.xml',
        'data/intrest_tag.xml',
        'views/res_config_settings.xml',
        'views/technical_job_checklist_views.xml',
        'views/technical_job_sale_template_views.xml',
        'security/ir.model.access.csv',
    ],
    "assets": {
        "web.assets_backend": ["roc_custom/static/src/js/purchase_stock_widget.js",
                               "roc_custom/static/src/js/widget.js",
                               #"roc_custom/static/src/js/calendar_color_assignation.js",
                               "roc_custom/static/src/css/custom_css.css"],
        "web.assets_qweb": ["roc_custom/static/src/xml/pos_receipt.xml",
                            "roc_custom/static/src/xml/template.xml",
                            "roc_custom/static/src/xml/template_stock_wid.xml",
                            #"roc_custom/static/src/xml/calendar_job_view.xml",
                            "roc_custom/static/src/xml/purchase_stock.xml"],
        'point_of_sale.assets': [
            'roc_custom/static/src/js/pos_customizations.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
