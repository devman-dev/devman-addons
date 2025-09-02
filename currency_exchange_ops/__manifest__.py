
{
    "name": "Currency Exchange Operations",
    "summary": "Registro contable de compra/venta de divisas con spread",
    "version": "17.0.1.0.0",
    "author": "PagoFlex / Alejandro",
    "website": "https://example.com",
    "depends": ["account", "base"],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/menu.xml",
        "views/currency_exchange_operation_views.xml",
        "views/res_company_views.xml"
    ],
    "license": "LGPL-3",
    "application": True,
    "installable": True
}
