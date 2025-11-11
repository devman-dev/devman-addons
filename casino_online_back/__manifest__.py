{
    'name': 'Casino Base',
    'version': '1.0.0',
    'summary': 'Base para la gestión de jugadores y juegos de casino',
    'description': 'Incluye modelos personalizados para onboarding de jugadores, juegos y sesiones.',
    'author': 'Tu Empresa',
    'depends': ['base', 'product', 'account', 'website_sale'],
    'data': [
        # 'views/player_views.xml',
        'views/game_views.xml',
        'views/session_views.xml',
        'views/withdrawals_views.xml',
        # 'views/player_signup_visibility.xml',
        'views/account_move.xml',
        'views/bet_limits_views.xml',
        'views/res_company_views.xml',
        'wizard/casino_session_report_wizard_views.xml',
        'views/global_report_views.xml',
        'views/menus.xml',
        'wizard/casino_session_report_wizard_views.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml'
        
        #'data/assign_signup_group.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "casino_online_back/static/src/**/*",
        ],
    },
    "post_init_hook": "create_bet_limits_for_all_partners",
    'installable': True,
    'application': True,
}
