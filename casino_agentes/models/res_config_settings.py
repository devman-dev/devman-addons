# -*- coding: utf-8 -*-
from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Campo para seleccionar la compañía a configurar
    agent_company_id = fields.Many2one(
        'res.company', 
        string='Compañía',
        help="Seleccioná la compañía para configurar sus ajustes de comisionamiento.",
        default=lambda self: self.env.company
    )

    # Campos relacionados a la compañía seleccionada
    commission_mode = fields.Selection(
        related='agent_company_id.commission_mode', 
        readonly=False,
        string='Modo de comisionamientos'
    )
    agent_commission_percent_default = fields.Float(
        related='agent_company_id.agent_commission_percent_default', 
        readonly=False,
        string='Porcentaje de comisión por defecto'
    )

    # Recordar la última compañía seleccionada por usuario
    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()
        company_id = int(icp.get_param(f'casino.agent.company_id.user_{self.env.user.id}', default=str(self.env.company.id)) or self.env.company.id)
        if company_id:
            res['agent_company_id'] = company_id
        return res

    def set_values(self):
        super().set_values()
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param(f'casino.agent.company_id.user_{self.env.user.id}', self.agent_company_id.id or self.env.company.id)


