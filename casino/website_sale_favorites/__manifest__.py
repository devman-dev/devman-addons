# -*- coding: utf-8 -*-
{
    "name": "Website Sale - Favorites",
    "summary": "Permite a los usuarios marcar productos como favoritos en el Website y verlos en /my/favorites",
    "version": "18.0.1.0.0",
    "category": "Website/Website",
    "website": "https://example.com",
    "author": "ChatGPT",
    "license": "LGPL-3",
    "depends": ["website", "website_sale", "portal"],
    "data": [
        "security/product_favorite_security.xml",
        "security/ir.model.access.csv",
        "views/templates.xml",
    ],
    "assets": {
        # Estilos; el JS se inyecta inline desde views/templates.xml
        "web.assets_frontend": [
            "website_sale_favorites/static/src/scss/favorite.scss",
        ],
    },
    "installable": True,
    "application": False,
}