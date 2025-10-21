{
    "name": "Maintenance Custom Fela",
    "summary": "Extensiones de configuración para Maintenance (view_vendor 0/1, Sitios y Sectores)",
    "version": "18.0.1.0.0",
    "author": "Devman3",
    "website": "",
    "category": "Maintenance",
    "license": "LGPL-3",
    "depends": [
        "maintenance",
        "dev_maintenance_purchase_agreement",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/maintenance_request_views.xml",
        "views/maintenance_site_views.xml",
        "data/maintenance_site_data.xml",
    ],
    "application": True,
    "installable": True,
    "auto_install": False,
}