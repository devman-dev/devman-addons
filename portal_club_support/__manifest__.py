{
    "name": "Portal Club Support",
    "version": "18.0.1.3.0",
    "category": "Website/Portal",
    "summary": "Portal para registro de usuario y selección de clubes de apoyo",
    "description": """
Portal Club Support - JogaJunto
================================

Módulo que implementa en el portal de Odoo una experiencia de registro
y selección de clubes para plataformas de juegos y apuestas.

Funcionalidades:
- Registro de datos personales del usuario (nombre, CPF, email, fecha de nacimiento)
- Categorías de juego configurables desde backend
- Clubes disponibles por categoría con comisiones
- Selección de club para apoyar en cada categoría
- Panel de resumen en /my/club-support
- Diseño responsive con estética deportiva brasileña
    """,
    "author": "Hitofusion",
    "website": "https://hitofusion.com",
    "license": "LGPL-3",
    "depends": [
        "portal",
        "website",
        "contacts",
        # ODOO18_PORTAL_FIX: portal_templates.xml inherits auth_signup.login.
        "auth_signup",
        # FEDERATION_CLUB_PICKER: source catalogue for searchable club fields.
        "casino_federacion_club",
        # FEATURED_GAMES: game catalogue and website publication fields.
        "casino_online_back",
        "website_sale",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/game_category_views.xml",
        "views/club_views.xml",
        "views/preference_views.xml",
        "views/res_partner_views.xml",
        "views/menu_views.xml",
        "views/portal_templates.xml",
        "data/demo_data.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "portal_club_support/static/src/scss/portal_club_support.scss",
            "portal_club_support/static/src/js/portal_club_support.js",
        ],
    },
    "demo": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
