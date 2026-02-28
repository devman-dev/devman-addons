# -*- coding: utf-8 -*-
{
    'name': 'Project Goals Portal Dashboard',
    'version': '19.0.1.0.0',
    'category': 'Project',
    'summary': 'Dashboard público de objetivos de proyectos con KPIs de cumplimiento',
    'description': """
        Portal Dashboard para Objetivos de Proyectos
        ============================================
        Este módulo extiende el portal de Odoo para mostrar:
        * Lista de todos los objetivos/metas de proyectos
        * KPIs de objetivos por estado (alcanzados, en progreso, pendientes)
        * Vista detallada de cada objetivo con su progreso
        * Acceso público sin necesidad de login
        
        Los visitantes pueden ver el progreso y cumplimiento de los objetivos
        organizacionales actuales.
    """,
    'author': 'Tu Nombre',
    'depends': ['project', 'portal', 'website'],
    'data': [
        'security/ir.model.access.csv',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'project_goals_portal_dashboard/static/src/css/portal_goals_dashboard.css',
            'project_goals_portal_dashboard/static/src/js/portal_goals_dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
