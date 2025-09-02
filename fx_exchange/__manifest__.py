# -*- coding: utf-8 -*-
{
    'name': 'Currency Exchange Ops',
    'version': '1.0.0',
    'summary': 'Gestión de operaciones de cambio de moneda',
    'description': '',
    'author': 'Tu Empresa',
    'website': 'https://tuempresa.com',
    'category': 'Accounting',
    'depends': ['base', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/currency_exchange_operation_views.xml',
        'views/menu.xml',
        'views/res_company_views.xml'
    ],
    'installable': True,
    'application': False
}
