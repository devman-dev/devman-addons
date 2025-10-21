{
    'name': 'Website Slides Adaptive Learning',
    'version': '1.0',
    'category': 'Website/eLearning',
    'summary': 'Extensión adaptativa para el módulo de eLearning',
    'description': """Capacidades adaptativas para website_slides""",
    'author': 'Tu Nombre',
    'website': 'https://www.tuwebsite.com',
    'depends': ['website_slides'],
    'data': [
        'security/ir.model.access.csv',  # Ya funciona
        'views/student_dashboard.xml',  # Ya funciona
        'views/teacher_dashboard.xml',  # Ya funciona
        'views/slide_views.xml',  # Ya funciona
        'demo/demo.xml'  # Agregando datos de demostración
    ],
    'assets': {
        'web.assets_frontend': [
            'website_slides_adaptive/static/src/js/adaptive_ui_engine.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
