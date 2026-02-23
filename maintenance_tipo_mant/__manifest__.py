# -*- coding: utf-8 -*-
{
    'name': 'Maintenance Request Extension',
    'version': '18.0.1.0.0',
    'category': 'Maintenance',
    'summary': 'Agrega campo tipo_mant a solicitudes de mantenimiento',
    'description': """
Extensión del módulo de mantenimiento
====================================

* Agrega el campo tipo_mant (texto) a maintenance.request
* Campo visible en formulario y lista
* Preparado para actualización vía API
""",
    'author': 'devman2',
    'depends': ['maintenance'],
    'data': [
        'views/maintenance_request_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
