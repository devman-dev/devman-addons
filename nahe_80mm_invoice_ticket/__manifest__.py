# -*- coding: utf-8 -*-
{
    "name": "nahe_80mm_invoice_ticket",
    "summary": "Permite imprimir el ticket factura de 80mm desde el backend sin estar en el POS.",
    "description": """
Permite imprimir el ticket factura de 80mm desde el backend sin estar en el POS.
Testeado en Odoo 16 Localización adhoc.
    """,
    "author": "Nähe Consulting Group",
    "website": "http://www.nahe.com.ar",
    "category": "Sales",
    "version": "17.0.1.0.0",
    "license": "LGPL-3",
    "depends": [
        "base",
        "sale",
        "account",
        "l10n_ar_afipws_fe",
    ],
    "data": [
        "views/views.xml",
        "views/templates.xml",
        "views/afip_view.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
