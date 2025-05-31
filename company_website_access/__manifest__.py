{
    'name': 'Company Website Links',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Agrega enlaces de website específicos por compañía',
    'description': """
        Este módulo extiende el modelo res.company para agregar:
        - Campo de enlace personalizable
        - Botón para probar enlaces
        - Generador automático de URLs por compañía
        - Campo de notas alternativas
    """,
    'author': 'Hito',
    'website': 'https://www.tuwebsite.com',

    'depends': ['base', 'website', 'website_maintenance_hr'],

    'external_dependencies': {
        'python': ['qrcode', 'pillow'],
    },
    'data': [
        'views/res_company_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}