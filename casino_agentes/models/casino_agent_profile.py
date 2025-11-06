from odoo import api, fields, models

class CasinoAgentProfile(models.Model):
    _name = "casino.agent.profile"
    _description = "Perfil de Agentes (Comisiones)"
    _rec_name = "name"
    _order = "company_id, name"

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    commission_mode = fields.Selection([
        ('certificate', 'Certificado'),
        ('free', 'Libre'),
    ], required=True, default='certificate')
    agent_commission_percent_default = fields.Float(string="Porcentaje de comisión por defecto")

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'Ya existe un perfil con el mismo nombre para esta compañía.')
    ]
   