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
        'views/templates/strip_template.xml'
    ],
    'installable': True,
}
