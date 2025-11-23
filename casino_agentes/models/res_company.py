# -*- coding: utf-8 -*-
from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    commission_mode = fields.Selection([
        ('certificado', 'Certificado'),
        ('libre', 'Libre'),
    ], string='Modo',
       help='Modos de comisionamientos para los agentes',
       default='libre')

    agent_commission_percent_default = fields.Float(
        string='Porcentaje',
        help='Porcentaje por defecto que comisiona un agente. Ej.: 2 para 2%.',
        default=2.0,
    )
