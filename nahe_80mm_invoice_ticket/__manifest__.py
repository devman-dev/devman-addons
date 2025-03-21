# -*- coding: utf-8 -*-
{
    'name': "nahe_80mm_invoice_ticket",

    'summary': """
        Permite imprimir el ticket factura de 80mm desde el backend sin estar en el POS.""",

    'description': """
        Permite imprimir el ticket factura de 80mm desde el backend sin estar en el POS.
        Testeado en odoo 16 Localizacion adhoc.
    """,

    'author': "Nähe Consulring Group",
    'website': "http://www.nahe.com.ar",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Sale',
    'version': '16.0',

    # any module necessary for this one to work correctly
<<<<<<< HEAD
    'depends': ['base','sale','account','l10n_ar'],
=======
    'depends': ['base','sale','account','l10n_ar_afipws_fe'],
>>>>>>> 16.0_mati_m

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/afip_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
