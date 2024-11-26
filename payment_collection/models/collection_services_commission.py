from odoo import fields, models, api

from odoo.exceptions import ValidationError


class CollectionServicesCommission(models.Model):
    _name = 'collection.services.commission'
    _rec_name = 'name_account'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, domain="[('check_origin_account','!=', True)]")
    services = fields.Many2one('product.template', string='Servicio', required=True, domain=[('collection_type', '=', 'service')])
    commission = fields.Float(string='Comisión', required=True)
    agent_services_commission = fields.One2many(
        'agent.commission.service', 'collection_services_commission_id', string='Comisión de servicios de agente', required=True
    )
    name = fields.Char()
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True)

    cbu = fields.Char('CBU')
    cvu = fields.Char('CVU')
    alias = fields.Char('Alias')
    name_account = fields.Char('Nombre Cuenta')
    cuit = fields.Char('CUIT')

    @api.depends('services')
    @api.depends_context('show_account_name')
    def _compute_display_name(self):
        for record in self:
            if self.env.context.get('show_servicio_name', False):
                # Mostrar el nombre del servicio
                name = record.services.display_name or 'Sin Servicio'
            elif self.env.context.get('show_account_name', False):
                # Mostrar el nombre de la cuenta
                name = record.name_account or 'Sin Nombre de Cuenta'
            else:
                # Nombre por defecto
                name = record.services.display_name or 'Registro Sin Nombre'
            record.display_name = name

    @api.onchange('services')
    def get_commission(self):
        for rec in self:
            if rec.services:
                rec.commission = rec.services.commission_default

    @api.onchange('commission', 'commission_app_rate', 'agent_services_commission')
    def commission_limit(self):
        for rec in self:
            if rec.commission > 0:
                total = rec.commission - rec.commission_app_rate
                total_ac = []
                for ac in rec.agent_services_commission:
                    total_ac.append(ac.commission_rate)

                total_agent_commission = sum(total_ac)

                if total_agent_commission > total:
                    raise ValidationError(
                        'El total de comisiones de agentes supera la cantidad de comisión. Para agregar un nuevo comisionista edite las cantidades anteriores.'
                    )

    @api.constrains('agent_services_commission')
    def delete_agent_commission_zero(self):
        for rec in self:
            for reg in rec.agent_services_commission:
                if reg.commission_rate == 0:
                    reg.unlink()
