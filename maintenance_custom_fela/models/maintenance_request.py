# -*- coding: utf-8 -*-
from odoo import api, fields, models

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'

    #Nuevos campos: Sitio y Sector
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
    
    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Limpiar el sector cuando cambia el sitio"""
        if self.site_id:
            return {'domain': {'sector_id': [('site_id', '=', self.site_id.id)]}}
        else:
            self.sector_id = False
            return {'domain': {'sector_id': []}}
#Boton finalizar tarea
    def action_mark_done(self):
        stage_done = self.env['maintenance.stage'].search([('done', '=', True)], limit=1)
        for rec in self:
            if stage_done:
                rec.stage_id = stage_done.id
            rec.message_post(body=f"✅ Solicitud marcada como realizada por {self.env.user.name}")

        # 🔁 Redirige a la vista kanban de mantenimiento
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.request',
            'view_mode': 'kanban',
            'target': 'current',
            'name': 'Solicitudes de Mantenimiento',
        }
