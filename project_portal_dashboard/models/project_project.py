# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    def _compute_access_url(self):
        """Genera la URL del portal para cada proyecto"""
        super(ProjectProject, self)._compute_access_url()
        for project in self:
            project.access_url = f'/my/project/{project.id}'

    def _get_share_url(self, redirect=False, signup_partner=False, pid=None):
        """
        Sobrescribe el método para personalizar la URL compartida
        """
        self.ensure_one()
        return f'/my/project/{self.id}'
