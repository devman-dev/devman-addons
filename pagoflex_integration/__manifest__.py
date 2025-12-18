{
    "name": "Pagoflex Integration Base",
    "version": "17.0.1.0.0",
    "category": "Tools",
    "summary": "Base module to integrate Banco de Comercio (BDC Conecta) endpoints via OpenAPI/Swagger",
    "description": "BDC Conecta integration scaffold for Odoo 17.\n\n"
                   "Features:\n"
                   "- Company-level configuration (base URL, auth parameters).\n"
                   "- Endpoint registry (manual or imported from an OpenAPI JSON).\n"
                   "- Secure token storage (system parameters) + automatic refresh helper.\n"
                   "- Test console wizard to execute endpoints and inspect responses.\n"
                   "- Request/response logging for traceability.\n\n"
                   "Note: This module is an integration framework. You can extend it with business flows specific to your project.",
    "author": "Hitofusion",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/bdc_menu.xml",
        "views/bdc_config_views.xml",
        "views/bdc_endpoint_views.xml",
        "views/bdc_log_views.xml",
        "wizard/bdc_test_call_wizard_views.xml",
        "wizard/bdc_import_openapi_wizard_views.xml",
        "data/ir_cron.xml"
    ],
    "application": False,
    "installable": True
}
