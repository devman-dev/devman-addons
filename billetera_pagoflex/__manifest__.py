{
    'name': 'Billetera PagoFlex',
    'version': '1.0',
    'description': '',
    'summary': '',
    'author': 'DevMan',
    'website': '',
    'license': 'LGPL-3',
    'category': '',
    'depends': ['payment_collection', 'website'],
    'data': [
        'views/billetera.xml',
        'views/movimientos.xml',
    ],
    'auto_install': False,
    'application': False,
    'assets': {
        'web.assets_frontend': [
            'billetera_pagoflex/static/src/components/**/*',
        ]
    },
}
