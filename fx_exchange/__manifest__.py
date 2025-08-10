# -*- coding: utf-8 -*-
{
    "name": "FX Exchange",
    "version": "1.0.2",  # Incremented version
    "summary": "Foreign Exchange Operations Management with Contact Tracking",
    "description": """
        Module for managing foreign exchange operations with contact tracking.
        Features:
        - Contact association for each operation
        - Automatic activity creation for contacts
        - Enhanced search and grouping by contact
        - Contact information display in operations
        - Mail thread integration with chatter
        - Automatic notifications for state changes
        - Configuration settings for FX operations
    """,
    "author": "Your Company",
    "website": "https://www.yourcompany.com",
    "category": "Accounting",
    "depends": ["base", "account", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/fx_operation_views.xml",
        "views/res_config_settings_views.xml",  # Added line for configuration settings
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "application": False,
}
