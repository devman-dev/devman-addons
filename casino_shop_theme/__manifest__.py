{
    'name': 'Casino Shop Theme',
    'version': '18.0.1.0.0',
    'category': 'Website/Theme',
    'summary': 'Casino lobby redesign for /shop — modern, compact, premium',
    'description': """
        Comprehensive redesign of the /shop page for casino.juegos.asartorio.online.
        - Search bar + providers button
        - Dynamic category pills (from product.public.category)
        - Horizontal carousels per category with game cards
        - Real games (Kinagol, Senagol, Raspaniha) + "BREVE" placeholders
        - Hover effects, "Jugar" button, player count indicator
        - Favorites integration
        - Mobile swipe support
    """,
    'author': 'Hitofusion',
    'website': 'https://hitofusion.com',
    'license': 'LGPL-3',
    'depends': [
        'website_sale',
        'casino_online',
        'casino_online_back',
    ],
    'data': [
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'casino_shop_theme/static/src/css/casino_shop.css',
            'casino_shop_theme/static/src/js/casino_shop.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}