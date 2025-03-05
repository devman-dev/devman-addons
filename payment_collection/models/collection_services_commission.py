from odoo import fields, models, api

from odoo.exceptions import ValidationError


class CollectionServicesCommission(models.Model):
    _name = 'collection.services.commission'
    _rec_name = 'name_account'
    _order = 'customer asc'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, domain="[('check_origin_account','!=', True)]")
    services = fields.Many2one('product.template', string='Servicio', required=True, domain=[('collection_type', '=', 'service')])
    commission = fields.Float(string='Comisión', required=True, digits=(16, 3))
    agent_services_commission = fields.One2many(
        'agent.commission.service', 'collection_services_commission_id', string='Comisión de servicios de agente', required=True
    )
    name = fields.Char()
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True, digits=(16, 3))
    bank_id = fields.Many2one('res.bank', string='Banco', required=True)
    cbu = fields.Char('CBU')
    cvu = fields.Char('CVU')
    alias = fields.Char('Alias')
    name_account = fields.Char('Nombre Cuenta')
    cuit = fields.Char('CUIT')
    bank_accounts = fields.Many2one('account.bank.pagoflex', string='Cuenta Bancaria', required=True)
    bank_accounts_ids = fields.Many2many('account.bank.pagoflex',string='Cuentas Bancarias', relation="account_bank2")

    @api.onchange('bank_id')
    def _get_bank_accounts(self):
        for rec in self:
            if rec.bank_id:
                accounts_ids = self.env['account.bank.pagoflex'].search([('bank_id', '=', rec.bank_id.id)])
                rec.bank_accounts_ids = accounts_ids.ids
            else:
                rec.bank_accounts_ids = False

    @api.onchange('bank_accounts')
    def _get_bank_accounts_data(self):
        for rec in self:
            if rec.bank_accounts:
                rec.cbu = rec.bank_accounts.cbu
                rec.cvu = rec.bank_accounts.cvu
                rec.alias = rec.bank_accounts.alias
                rec.name_account = rec.bank_accounts.name
                rec.cuit = rec.bank_accounts.cuit
                domain = [('bank_accounts', '=', rec.bank_accounts.id)]
                if rec.id:
                    domain.append(('id', '!=', rec.id))

                exist_another = self.env['collection.services.commission'].search(domain)
                if len(exist_another) > 0:
                    self.env['bus.bus']._sendone(
                        self.env.user.partner_id,
                        'simple_notification',
                        {
                            'type': 'warning',
                            'message': 'Ya existe otro registro con esta cuenta bancaria.',
                            'title': 'Advertencia',
                            'sticky': False,
                        },
                    )
            else:
                rec.cbu = False
                rec.cvu = False
                rec.alias = False
                rec.name_account = False
                rec.cuit = False

    @api.depends('services')
    @api.depends_context('show_account_name')
    def _compute_display_name(self):
        for record in self:
            if self.env.context.get('show_servicio_name', False):
                # Mostrar el nombre del servicio
                name = record.services.display_name or 'Sin Servicio'
            elif self.env.context.get('show_account_name', False):
                # Mostrar el nombre de la cuenta
                name = f'{record.name_account} - {record.customer.name}' or 'Sin Nombre de Cuenta'
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

    # Sobrescribir el método copy
    def copy(self, default=None):
        default = dict(default or {})
        # Llamar al método copy original
        new_record = super(CollectionServicesCommission, self).copy(default)

        # Copiar los registros One2many relacionados
        for agent_service in self.agent_services_commission:
            agent_service.copy({'collection_services_commission_id': new_record.id})

        return new_record
