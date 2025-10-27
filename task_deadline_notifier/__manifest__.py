# -*- coding: utf-8 -*-
{
    'name': "Task Deadline Notifier",
    'summary': "Sends deadline reminders for project tasks",
    'description': """This module automatically sends email reminders to users 
responsible for project tasks when deadlines are approaching or overdue.
It helps ensure timely task completion and better team accountability.
    """,
    'author': "Ankit",
    'category': 'Project',
    'version': '18.0',
    'license': 'LGPL-3',
    'depends': ['base', 'project'],
    'data': [
        'data/mail_templates.xml',
        'data/cron_jobs.xml'
    ],
    'images': ['static/description/icon.jpeg'],
    'installable': True,
    'auto_install': False,
    'application': True
}
