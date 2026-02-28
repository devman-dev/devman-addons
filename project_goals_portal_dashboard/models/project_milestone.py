# -*- coding: utf-8 -*-

from odoo import models


class ProjectMilestone(models.Model):
    _inherit = 'project.milestone'

    def _compute_access_url(self):
        """Genera la URL del portal para cada objetivo"""
        for goal in self:
            goal.access_url = f'/goal/{goal.id}'
