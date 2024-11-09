from odoo import fields, models, api


class AgentCommissionService(models.Model):
    _name = 'agent.commission.service'
    _rec_name = 'agent'
    
    agent = fields.Many2one('res.partner', string='Agente', required=True)
    commission_rate = fields.Float(string='Tasa de Comisión', required=True)
    collection_services_commission_id = fields.Many2one('collection.services.commission')
    