{
    'name': 'PagoFlex - Collection Transaction on Payment Sent',
    'version': '17.0.1.0.1',
    'author': 'PagoFlex / Devman',
    'website': 'https://example.com',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'summary': 'Odoo 17: abre collection.transaction al marcar pago como enviado',
    'depends': [
        'account',
    ],
    'data': [
        'views/account_payment_views.xml',
    ],
    'installable': True,
    'application': False,
}
