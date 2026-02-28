# -*- coding: utf-8 -*-
{
    'name': 'Project Portal Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Dashboard de proyectos en el portal con KPIs por estado',
    'description': """
        Portal Dashboard para Proyectos
        ================================
        Este módulo extiende el portal de Odoo para mostrar:
        * Lista de todos los proyectos
        * KPIs de proyectos por estado
        * Vista detallada de cada proyecto
    """,
    'author': 'Tu Nombre',
    'depends': ['project', 'portal', 'website'],
    'data': [
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'project_portal_dashboard/static/src/css/portal_dashboard.css',
            'project_portal_dashboard/static/src/js/portal_dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
