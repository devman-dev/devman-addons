from odoo import models, fields, api
from datetime import datetime, timedelta

class TaskDeadlineNotifier(models.Model):
    _inherit = 'project.task'

    def send_deadline_notifications(self):
        today = fields.Date.today()
        tasks = self.search([
            ('date_deadline', '!=', False),
            ('stage_id', '!=', 'done'),
            ('user_ids', '!=', False)
        ])

        for task in tasks:
            if task.date_deadline.date() in [today, today + timedelta(days=1)]:
                self._notify_users(task)

    def _notify_users(self, task):
        mail_template = self.env.ref('task_deadline_notifier.email_template_task_deadline')
        for user in task.user_ids:
            mail_template.send_mail(task.id, force_send=True)

