# -*- coding: utf-8 -*-
from odoo import models, fields

class MaintenanceRequest(models.Model):
    _inherit = 'maintenance.request'
    
    tipo_mant = fields.Char(
        string='Tipo de Mantenimiento',
        help='Tipo de mantenimiento que llega desde las notas'
    )
