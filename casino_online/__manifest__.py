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
        'views/templates/transactions_template.xml',
        'views/templates/website_header.xml',
        'views/templates/strip_template.xml',
        'views/templates/portal_mis_limites_partial.xml',
        'views/res_partner_form_casino_online.xml',
        'views/templates/user_options_template.xml',
        'data/balance_cron.xml',
    ],
    "assets": {
        # CSS puede ir en el bundle frontend estándar
        "web.assets_frontend": [
            # "casino_online/static/src/scss/withdrawals.scss",
        ],
        # JS que depende de web.public.widget / web.Dialog debe ir en lazy
        "web.assets_frontend_lazy": [
            ("include", "web.assets_frontend"), # Asegura que los assets core del frontend se carguen para las dependencias
            "casino_online/static/src/js/withdrawal_modal.js",
        ],
    },
    'installable': True,
}
