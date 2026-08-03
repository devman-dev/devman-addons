{
    "name": "Casino Federacion Club",
    "version": "18.0.2.0.0",
    "category": "Casino",
    "summary": "Gestion de federaciones y clubes para Casino",
    "author": "Hitofusion",
    "depends": ["casino_online_back"],
    "data": [
        "security/ir.model.access.csv",
        "views/casino_federation_views.xml",
        "views/casino_club_views.xml",
        "views/menu.xml",
        "data/brazil_football_data.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
