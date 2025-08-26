{
    'name': 'Casino Online',
    'category': 'Website/eCommerce',
    'summary': 'Online casino platform with eCommerce integration',
    'version': '1.0.0',
    'license': 'LGPL-3',
    'author': 'Gerlin Matos',
    'website': 'https://github.com/gerlinmatos',
    'description': """
        Casino Online Module
        ===================
        ...
    """,
    'images': ['static/description/icon.png'],
    'depends': ['website_sale', 'portal', 'account', 'payment', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/templates/user_options_template.xml',
        'views/templates/transactions_template.xml',
        'views/templates/website_header.xml',
        'views/templates/strip_template.xml',
        'views/templates/portal_mis_limites_partial.xml',
        'views/res_partner_form_casino_online.xml'
    ],
    "assets": {
        "web.assets_frontend": [
            "casino_online/static/src/**/*",
        ]
    },
    'installable': True,
}
