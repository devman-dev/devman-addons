{
    'name': 'Survey XLSX',
    'version': '17.0.0.0.1',
    'summary': 'Exportar datos de encuestas a archivos Excel',
    'description': 'Este módulo permite exportar datos de encuestas a archivos XLSX.',
    'author': 'Devman',
    'website': '',
    'category': 'Tools',
    'depends': ['base','survey','report_xlsx'],
    'data': [
        'views/survey_survey_view_form.xml',
        # 'views/action_survey_export_xlsx.xml'
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}