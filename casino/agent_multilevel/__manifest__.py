# -*- coding: utf-8 -*-
{
    "name": "Agent Multilevel",
    "version": "18.0.1.0.0",
    "summary": "Jerarquía multinivel de agentes y vinculación de jugadores",
    "description": """
        Agentes multinivel para gestionar subagentes y jugadores.
        - Campos en res.partner:
        * is_agent, is_player
        * parent_agent_id / child_agent_ids (jerarquía de agentes)
        * agent_id / managed_player_ids (vínculo jugadores↔agente)
    """,
    "author": "Hitofusion",
    "license": "LGPL-3",
    "depends": ["base", "contacts", "web", "product", "website_sale", "casino_online_back"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/agent_hierarchy_view.xml",
        "views/product_category_views.xml",
        "views/product_template_views.xml",
        "views/product_template_casino_views.xml",
        "wizard/public_category_commission_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "agent_multilevel/static/src/css/agent_hierarchy.css",
            "agent_multilevel/static/src/css/horizontal_organigrama.css",
            "agent_multilevel/static/src/js/agent_hierarchy.js",
            "agent_multilevel/static/src/xml/agent_hierarchy_templates.xml",
        ],
    },
    "application": False,
    "installable": True,
}
