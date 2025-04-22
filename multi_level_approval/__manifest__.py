{
    "name": "Odoo Approval",
    "version": "18.0.1.0.0",
    "category": "Approvals",
    "summary": """
    Create and validate approval requests.
    Each request can be approved by many levels of different managers
    """,
    "live_test_url": "https://demo18.domiup.com",
    "author": "Domiup (domiup.contact@gmail.com)",
    "price": 80,
    "currency": "USD",
    "license": "OPL-1",
    "support": "domiup.contact@gmail.com",
    "website": "https://demo18.domiup.com",
    "depends": ["mail", "product"],
    "data": [
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "security/security.xml",
        "security/ir.model.access.csv",
        # wizard
        "wizard/refused_reason_views.xml",
        "views/multi_approval_type_views.xml",
        "views/multi_approval_views.xml",
        # Add actions after all views.
        "views/actions.xml",
        # Add menu after actions.
        "views/menu.xml",
    ],
    "images": ["static/description/banner.jpg"],
    "test": [],
    "demo": [],
    "installable": True,
    "application": True,
}
