{
    'name': 'Casino Online',
    'category': 'Website/eCommerce',
    'summary': 'Online casino platform with eCommerce integration',
    'version': '1.0.0',
    'license': 'LGPL-3',
    'author': 'Gerlin Matos',
    'website': 'https://github.com/gerlinmatos',
    'description': 'Online casino platform with eCommerce integration.',
    'images': ['static/description/icon.png'],
    'depends': ['website_sale', 'portal', 'account', 'payment', 'web', 'auth_signup'],
    'data': [
        'security/ir.model.access.csv',
        'views/templates/portal_minha_conta.xml',
        'views/templates/transactions_template.xml',
        'views/templates/website_header.xml',
        'views/templates/strip_template.xml',
        'views/templates/portal_mis_limites_partial.xml',
        'views/res_partner_form_casino_online.xml',
        'views/templates/user_options_template.xml',
        'views/web_login_inherit.xml',
        # 'data/balance_cron.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "casino_online/static/src/css/user_menu.css",
        ],
        # JS que debe estar disponible en frontend
        "web.assets_frontend": [
            "casino_online/static/src/js/wallet_balance.js",
            "casino_online/static/src/js/portal_minha_conta.js",
            "casino_online/static/src/css/portal_minha_conta.css",
            # "casino_online/static/src/js/movements_live.js",
        ],
        # JS lazy-loaded para optimización
        "web.assets_frontend_lazy": [
            "casino_online/static/src/js/transaction_history.js",
            "casino_online/static/src/js/withdrawal_list.js",
            "casino_online/static/src/js/withdrawal_modal.js",
            "casino_online/static/src/js/withdrawal_form.js",
            "casino_online/static/src/js/bank_list.js",
            "casino_online/static/src/js/limits_form.js",
        ],
    },
    'installable': True,
}
