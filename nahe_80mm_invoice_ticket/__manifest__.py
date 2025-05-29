# -*- coding: utf-8 -*-
{
    "name": "nahe_80mm_invoice_ticket",
    "summary": "Permite imprimir el ticket factura de 80mm desde el backend sin estar en el POS.",

    "author": "Nähe Consulting Group",
    "website": "http://www.nahe.com.ar",
    "category": "Sales",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "depends": [
        "base",
        "sale",
        "account",
        "l10n_ar_afipws_fe",
    ],
    "data": [
        "views/views.xml",

        "views/afip_view.xml",
        "reports/report_ticket_80mm.xml",
    ],
    "assets": {},
    "installable": True,
    "application": False,
}
