{
    'name': 'Casino Base',
    'version': '1.0',
    'summary': 'Base para la gestión de jugadores y juegos de casino',
    'description': 'Incluye modelos personalizados para onboarding de jugadores, juegos y sesiones.',
    'author': 'Tu Empresa',
    'depends': ['base', 'product', 'account'],
    'data': [
        'views/player_views.xml',
        'views/game_views.xml',
        'views/session_views.xml',
        'views/player_signup_visibility.xml',
        'views/account_move.xml',
        'views/menus.xml',
        
        #'data/assign_signup_group.xml',
    ],
    'installable': True,
    'application': True,
}
