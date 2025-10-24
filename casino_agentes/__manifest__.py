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
        # Seguridad y accesos primero
        "security/ir.model.access.csv",
        "security/agent_liquidation_access.xml",
        # Vistas y acciones que serán referenciadas por menús
        "views/res_partner_views.xml",
        "views/agent_hierarchy_view.xml",              # define action_agent_hierarchy_widget y action_agent_hierarchy
        "views/agent_liquidation_wizard_views.xml",    # define action_agent_liquidation_wizard
        "views/agent_liquidation_views.xml",           # define action_agent_liquidation
        "views/product_category_views.xml",            # define public_category_commission_action
        "views/product_template_views.xml",
        "views/product_template_casino_views.xml",
        "wizard/public_category_commission_wizard.xml",
        # Menús al final para que todas las acciones existan
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "casino_agentes/static/src/css/agent_hierarchy.css",
            "casino_agentes/static/src/css/horizontal_organigrama.css",
            "casino_agentes/static/src/js/agent_hierarchy.js",
            "casino_agentes/static/src/xml/agent_hierarchy_templates.xml",
        ],
    },
    "application": False,
    "installable": True,
}
