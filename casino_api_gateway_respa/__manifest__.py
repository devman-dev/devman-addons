{
    "name": "Casino API Gateway",
    "summary": "API estandar multi-proveedor para casino con auditoria e idempotencia",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "casino_online",
        "casino_online_back"
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/casino_api_provider_data.xml",
        "views/casino_api_menus.xml",
        "views/casino_api_provider_views.xml",
        "views/casino_api_operation_views.xml",
        "views/casino_api_audit_event_views.xml"
    ],
    "installable": True,
    "application": True
}
