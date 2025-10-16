# -*- coding: utf-8 -*-
from odoo import api, fields, models

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    # Campo existente
    show_vendor = fields.Boolean(
        string='Mostrar proveedor',
        compute='_compute_show_vendor',
        compute_sudo=True,
        store=False
    )

    # Nuevos campos: Sitio y Sector
    site_id = fields.Many2one(
        'maintenance.site',
        string='Sitio',
        tracking=True,
        help='Sitio donde se realizará el mantenimiento'
    )
    
    sector_id = fields.Many2one(
        'maintenance.sector',
        string='Sector',
        domain="[('site_id', '=', site_id)]",
        tracking=True,
        help='Sector específico dentro del sitio'
    )

    @api.depends_context('uid')
    def _compute_show_vendor(self):
        """Lee el parámetro global guardado en Configuración (Res Config Settings)."""
        icp = self.env['ir.config_parameter'].sudo()
        view_vendor = icp.get_param('maintenance_custom_fela.view_vendor', default='1')
        show = (view_vendor == '1')
        for record in self:
            record.show_vendor = show

    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Limpiar el sector cuando cambia el sitio"""
        if self.site_id:
            return {'domain': {'sector_id': [('site_id', '=', self.site_id.id)]}}
        else:
            self.sector_id = False
            return {'domain': {'sector_id': []}}