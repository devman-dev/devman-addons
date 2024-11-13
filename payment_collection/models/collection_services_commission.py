from odoo import fields, models, api


class CollectionServicesCommission(models.Model):
    _name = 'collection.services.commission'
    
    customer = fields.Many2one('res.partner', string='Cliente', required=True)
    services = fields.Many2one('product.template', string='Servicio', required=True, domain=['|',('collection_type', '=','operation'),('collection_type', '=','service')])
    commission = fields.Float(string='Comisión', required=True)
    agent_services_commission = fields.One2many('agent.commission.service','collection_services_commission_id', string='Comisión de servicios de agente', required=True)
    name = fields.Char()
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True, compute="get_last_app_commission")
    
    @api.depends('customer')
    def get_last_app_commission(self):
        last_app_commission = self.env['commission.app'].search([], order='date desc', limit=1)
        self.commission_app_rate = last_app_commission.commission_rate
    
    
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