from odoo import fields, models, api


class CollectionServicesCommission(models.Model):
    _name = 'collection.services.commission'
    
    customer = fields.Many2one('res.partner', string='Cliente', required=True)
    services = fields.Many2one('product.template', string='Servicio', required=True, domain=['|',('collection_type', '=','operation'),('collection_type', '=','service')])
    commission = fields.Float(string='Comisión', required=True)
    agent_services_commission = fields.One2many('agent.commission.service','collection_services_commission_id', string='Comisión de servicios de agente', required=True)
    name = fields.Char()
    
    def _compute_commission_rate(self):
        pass
    
    @api.constrains('customer', 'services')
    def _get_name(self):
        for r in self:
            r.name = f'{r.customer.name} - {r.services.name}'


    @api.onchange('services')
    def get_commission(self):
        for rec in self:
            if rec.services:
                rec.commission = rec.services.commission_default