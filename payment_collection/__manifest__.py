{
    'name': 'PagoFlex',
    'version': '1.0',
    'description': 'Module for PagoFlex',
    'summary': '',
    'author': 'DEV-MAN',
    'website': '',
    'license': 'LGPL-3',
    'category': 'account',
    'depends': ['base', 'contacts', 'stock','report_xlsx'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'data/data.xml',
        'report/report.xml',
        'report/collection_transaction.xml',
        'report/collection_transaction_commission.xml',
        'views/agent_commission_service.xml',
        'views/collection_services_commission.xml',
        'views/collection_transaction_commission.xml',
        'views/collection_transaction.xml',
        'views/collection_dashboard_customer.xml',
        'views/product_template.xml',
        'views/res_partner.xml',
        'views/menuitems.xml',
        'views/bank_statement_views.xml',
        'wizard/payment_wiz.xml',
        'wizard/report_agent_wiz.xml',
        'wizard/commi_trans_wiz.xml',
        'wizard/bank_movements_month.xml',
        'wizard/recalculate_button.xml',
    ],
    'demo': [''],
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_backend': [
            'payment_collection/static/src/js/*.js',
            'payment_collection/static/src/xml/*.xml',
        ]
    },
    'images': ['static/description/icon.png'],
}
