from odoo import fields, models, api

from odoo.exceptions import ValidationError


class CollectionServicesCommission(models.Model):
    _name = 'collection.services.commission'
    
    customer = fields.Many2one('res.partner', string='Cliente', required=True)
    services = fields.Many2one('product.template', string='Servicio', required=True, domain=['|',('collection_type', '=','operation'),('collection_type', '=','service')])
    commission = fields.Float(string='Comisión', required=True)
    agent_services_commission = fields.One2many('agent.commission.service','collection_services_commission_id', string='Comisión de servicios de agente', required=True)
    name = fields.Char()
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True)
    
    @api.onchange('customer')
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


    @api.onchange('commission','commission_app_rate','agent_services_commission')
    def commission_limit(self):
        for rec in self:
            total = rec.commission - rec.commission_app_rate
            total_ac = []
            for ac in rec.agent_services_commission:
                total_ac.append(ac.commission_rate)

            total_agent_commission = sum(total_ac)

            if total_agent_commission > total:
                raise ValidationError('El total de comisiones de agentes supera la cantidad de comisión. Para agregar un nuevo comisionista edite las cantidades anteriores.')



                # def action_notification(self):
    #     return {
    #         'type': 'ir.actions.client',
    #         'tag': 'display_notification',
    #         'params': {
    #             'title': 'Registrar marcación de salida',
    #             'message': 'Recordá registrar tu marcación de salida',
    #             'type': 'danger',
    #             'sticky': False
    #         }
    #     }

