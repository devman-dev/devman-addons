from odoo import fields, models, api
from datetime import datetime
import datetime as dt
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class CollectionTransaction(models.Model):
    _name = 'collection.transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'transaction_name'
    _order = 'id desc'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True)
    transaction_name = fields.Char(string='N° Transacción', tracking=True)
    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    commission = fields.Float(string='Comisión (%)')
    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)
    date = fields.Date(string='Fecha', tracking=True, default=datetime.now())
    description = fields.Text(string='Descripción', tracking=True)
    origin_account_cuit = fields.Char(string='CUIT origen', tracking=True, default=False)
    origin_account_cvu = fields.Char(string='CVU origen', tracking=True)
    origin_account_cbu = fields.Char(string='CBU origen', tracking=True)
    related_customer = fields.Char(string='Cliente Relacionado', tracking=True)
    amount = fields.Float(string='Monto', tracking=True, required=True)
    date_available_amount = fields.Date('Fecha del monto disponible')
    real_balance = fields.Float(string='Saldo Real')
    available_balance = fields.Float(string='Saldo Disponible', tracking=True)
    cbu_destination_account = fields.Char(string='CBU Destino', tracking=True, default=False)
    cvu_destination_account = fields.Char(string='CVU Destino', tracking=True, default=False)
    name_destination_account = fields.Char(string='Cta Destino', tracking=True)
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True)
    commission_app_amount = fields.Float(string='Monto de la App', tracking=True)
    cbu_check = fields.Char('Check cbu')
    previous_month = fields.Float('Mes Anterior', compute='compute_previous_month')
    count = fields.Integer('', default=0)
    alias_destination_account = fields.Char(string='Alias Destino')
    alias_origen = fields.Char(string='Alias Origen')
    transaction_state = fields.Selection(
        [
            ('falta_ejecutar', 'Falta Ejecutar'),
            ('ejecutada_faltan_datos', 'Ejecutada-Faltan Datos'),
            ('ejecutada_datos_completos', 'Ejecutada-Datos Completos'),
        ],
        string='Estado',
        default='falta_ejecutar',
    )
    collection_trans_type = fields.Selection(
        [('retiro', 'Mov. Retiro'), ('movimiento_interno', 'Mov. Interno'), ('movimiento_recaudacion', 'Acreditación')],
        default='movimiento_recaudacion',
        string='Tipo de Transacción',
    )
    withdrawal_operations = fields.Many2many('product.template', domain=[('collection_type', '=', 'operation')])
    alert_withdrawal = fields.Boolean()
    internal_notes = fields.Text()
    account_source = fields.Many2one('res.partner', string='Cuenta Origen')
    
    @api.onchange('account_source')
    def get_account_source_data(self):
        if self.account_source:
            self.sudo().write({
                'origin_account_cuit': self.account_source.cuit_account_source,
                'origin_account_cbu': self.account_source.cbu_account_source,
                'origin_account_cvu': self.account_source.cvu_account_source,
                'alias_origen': self.account_source.alias_account_source,
            })

    @api.onchange('transaction_name')
    def get_last_client(self):
        user_id = self.env.uid
        last_client = self.env['collection.transaction'].sudo().search([('create_uid', '=', user_id)], limit=1, order='id desc')
        if last_client and not self.transaction_name:
            self.sudo().write({'customer': last_client.customer.id, 'service': last_client.service.id})

    @api.onchange('amount')
    def withdrawal_amount(self):
        if self.collection_trans_type == 'retiro' or self.collection_trans_type == 'movimiento_interno':
            self.amount = self.amount * -1 if self.amount > 0 else self.amount

    @api.onchange('amount')
    def calculate_commission_app_amount(self):
        self.commission_app_amount = (self.commission_app_rate * self.amount) / 100

    @api.onchange('customer', 'service')
    def get_last_app_commission(self):
        self.commission_app_rate = self.service.commission_app_rate if self.service else 0

        # TRAEMOS DATOS DEL CLIENTE DESDE RES PARTNER.
        if self.customer:
            self.sudo().write({
                'account_source': self.customer.id,
                'cbu_destination_account':self.customer.cbu_destination,
                'cvu_destination_account': self.customer.cvu_destination,
                'alias_destination_account':self.customer.alias_destination,
                'name_destination_account': self.customer.name_account_destination,
                'internal_notes': self.customer.comment
            })

    @api.model
    def create(self, vals):
        if vals['count'] == 0:
            vals['transaction_name'] = self.env['ir.sequence'].next_by_code('collection.transaction') or ('New')
            bills_id = self.env['product.template'].sudo().search([('name', 'ilike', 'gastos')], limit=1)
            dict_transac = {
                'customer': vals['customer'],
                'transaction_name': str(vals['transaction_name']),
                'service': vals['service'],
                'date': vals['date'],
                'commission': vals['commission'],
                'operation': bills_id.id,
                'description': 'Comisión',
                'amount': ((vals['commission'] / 100) * vals['amount']) * -1,
                'origin_account_cuit': 0,
                'origin_account_cvu': 0,
                'origin_account_cbu': 0,
                'related_customer': 0,
                'cbu_destination_account': 0,
                'count': 1,
            }
            if not vals['collection_trans_type'] == 'retiro' and not vals['collection_trans_type'] == 'movimiento_interno':
                self.env['collection.transaction'].sudo().create(dict_transac)
        res = super(CollectionTransaction, self).create(vals)

        message = ('Se ha creado la siguiente transaccion: %s.') % (str(vals['transaction_name']))

        res.message_post(body=message)

        return res

    def _compute_account_move(self):
        pass

    @api.constrains('customer')
    def compute_commission_agent(self):
        for rec in self:
            for agent_service in rec.service.agent_services_commission:
                commission_amount = (agent_service.commission_rate * rec.amount) / 100
                if commission_amount > 0 and rec.count == 0:
                    rec.env['collection.transaction.commission'].sudo().create(
                        {
                            'date': rec.date,
                            'transaction_name': rec.transaction_name,
                            'operation_amount': rec.amount,
                            'payment_rest': commission_amount,
                            'customer': rec.customer.id,
                            'transaction_service': rec.service.id,
                            'transaction_operation': rec.operation.id,
                            'agent': agent_service.agent.id,
                            'commission_rate': agent_service.commission_rate,
                            'commission_amount': commission_amount,
                        }
                    )

    def _compute_generate_expense(self):
        pass

    @api.constrains('customer')
    def create_dashboard_customer(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_interno' or rec.count == 1:
                return
            today_date = dt.datetime.now().date()
            days_ago = dt.timedelta(days=2)
            customer = self.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id)])
            available_balance_ids = (
                self.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id), ('date', '<=', today_date - days_ago)])
            )
            avaiable_withdrawal_ids = (
                self.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id), ('collection_trans_type', '=', 'retiro')])
            )

            available_balance_list = [a.amount for a in available_balance_ids]
            available_withdrawal_list = [a.amount for a in avaiable_withdrawal_ids]
            real_balance_list = [c.amount if c.count != 1 else 0 for c in customer]
            commission_balance_list = [c.amount for c in customer if c.amount < 0 and c.collection_trans_type == 'movimiento_recaudacion']
            commission_app_rate_list = [c.commission_app_rate for c in customer]
            commission_app_amount_list = [c.commission_app_amount for c in customer]
            if customer:
                real_balance = sum(real_balance_list)
                withdrawal_balance = sum(available_withdrawal_list) * -1
                available_balance = sum(available_balance_list)
                commission_balance = sum(commission_balance_list)
                commission_app_rate = sum(commission_app_rate_list) / len(commission_app_rate_list)
                commission_app_amount = sum(commission_app_amount_list)
            else:
                real_balance = rec.real_balance
                available_balance = rec.available_balance
                if rec.commission < 0:
                    commission_balance = rec.commission
                else:
                    commission_balance = 0

            dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', rec.customer.id)], limit=1, order='id desc')

            if dashboard_customer:
                if rec.collection_trans_type == 'movimiento_recaudacion':
                    commission = rec.amount - ((rec.amount * rec.commission) / 100)
                    total_collection_balance = dashboard_customer.collection_balance + commission
                else:
                    total_collection_balance = dashboard_customer.collection_balance - withdrawal_balance
                dashboard_customer.sudo().write(
                    {
                        'customer': rec.customer.id,
                        'last_operation_date': datetime.now(),
                        'customer_real_balance': real_balance - commission_app_amount,
                        'customer_available_balance': available_balance - withdrawal_balance,
                        'commission_balance': commission_balance,
                        'collection_balance': total_collection_balance,
                        'commission_app_amount': commission_app_amount,
                        'commission_app_rate': commission_app_rate,
                    }
                )

            else:
                total_collection_balance = rec.amount - ((rec.amount * rec.commission) / 100)
                self.env['collection.dashboard.customer'].sudo().create(
                    {
                        'customer': rec.customer.id,
                        'customer_real_balance': real_balance - rec.commission_app_amount,
                        'customer_available_balance': available_balance,
                        'last_operation_date': datetime.now(),
                        'commission_balance': commission_balance,
                        'collection_balance': total_collection_balance,
                        'commission_app_amount': rec.commission_app_amount,
                        'commission_app_rate': rec.commission_app_rate,
                    }
                )

    @api.onchange('customer', 'amount')
    @api.constrains('amount')
    def _compute_real_balance_costumer(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1)
                rec.sudo().write({'real_balance': dashboard_customer.customer_real_balance})

    @api.onchange('amount', 'date', 'customer')
    def _compute_available_balance_costumer(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1)
                rec.sudo().write({'available_balance': dashboard_customer.customer_available_balance})
                if (rec.amount * -1) > rec.available_balance and rec.collection_trans_type == 'retiro':
                    rec.alert_withdrawal = True

            """  today_date = dt.datetime.now().date()
                days_ago = dt.timedelta(days=2)

                available_balance_ids = (
                    self.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id), ('date', '<=', today_date - days_ago)])
                )
                avaiable_withdrawal_ids = (
                    self.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id), ('collection_trans_type', '=', 'retiro')])
                )

                if available_balance_ids:
                    if avaiable_withdrawal_ids:
                        available_withdrawal_list = [a.amount for a in avaiable_withdrawal_ids]
                        withdrawal_balance = sum(available_withdrawal_list) * -1
                    else:
                        withdrawal_balance = 0

                    available_balance_list = [a.amount for a in available_balance_ids]
                    available_balance = sum(available_balance_list)
                    rec.available_balance = available_balance - withdrawal_balance
                    rec.date_available_amount = available_balance_ids[0].date"""

    @api.constrains('amount')
    def disable_alert_withdrawal(self):
        for rec in self:
            if rec.collection_trans_type == 'retiro' and rec.alert_withdrawal:
                rec.alert_withdrawal = False

    @api.onchange('service')
    def check_service(self):
        for rec in self:
            if not rec.service:
                rec.cbu_check = ''
                continue
            service_name = rec.service.display_name.lower()
            if service_name == 'cbu':
                rec.cbu_check = 'cbu'
            elif service_name == 'cvu':
                rec.cbu_check = 'cvu'

    @api.depends('date')
    def compute_previous_month(self):
        for rec in self:
            days = rec.date.day - 1
            start_date = rec.date - relativedelta(months=1, days=days)
            end_date = rec.date - relativedelta(days=days) - relativedelta(days=1)

            domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id)]

            previous_months = self.env['collection.transaction'].search(domain)
            rec.previous_month = sum([pm.amount for pm in previous_months])

    @api.model
    def open_commi_trans_wiz(self):
        return {
            'name': 'Reporte de agente',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'commi.trans.wiz',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.constrains('origin_account_cuit')
    def check_cuil(self):
        for rec in self:
            if self.count != 1:
                if rec.origin_account_cuit:
                    if rec.origin_account_cuit.isdigit():
                        pass
                    else:
                        rec.origin_account_cuit = rec.origin_account_cuit.replace('-', '').replace(' ', '')

                    if len(rec.origin_account_cuit) > 11 or len(rec.origin_account_cuit) < 11:
                        raise ValidationError(f'La longitud del campo CUIT es incorrecta.{len(rec.origin_account_cuit)}')

    @api.onchange('collection_trans_type', 'service')
    def no_commission_on_withdrawal(self):
        for rec in self:
            if rec.collection_trans_type == 'retiro' or rec.collection_trans_type == 'movimiento_interno':
                rec.commission = 0
            else:
                rec.commission = rec.service.commission

    @api.onchange('collection_trans_type')
    def set_default_operation(self):
        for rec in self:
            all_operations = self.env['product.template'].search([('collection_type', '=', 'operation')])
            if rec.collection_trans_type == 'movimiento_recaudacion':
                acreditacion = rec.operation.search([('name', 'ilike', 'acreditaci%')], limit=1)
                rec.operation = acreditacion.id

                rec.withdrawal_operations = all_operations.ids
            elif rec.collection_trans_type == 'retiro':
                extraccion = rec.operation.search([('name', 'ilike', 'extracc%')], limit=1)
                transferencia = rec.operation.search([('name', 'ilike', 'transferencia')], limit=1)
                operation_ids = []
                if extraccion:
                    operation_ids.append(extraccion.id)
                if transferencia:
                    operation_ids.append(transferencia.id)
                rec.operation = False
                rec.withdrawal_operations = operation_ids
            else:
                rec.withdrawal_operations = all_operations.ids

    # @api.constrains('origin_account_cbu', 'origin_account_cvu', 'cbu_destination_account')
    # def cant_numeros_cbu(self):
    #     if self.count != 1:
    #         if self.origin_account_cbu:
    #             if len(self.origin_account_cbu) != 22:
    #                 raise ValidationError(f'La longitud del campo CBU es incorrecta.{str(len(self.origin_account_cbu))}')
    #             if self.origin_account_cbu.isdigit():
    #                 pass
    #             else:
    #                 raise ValidationError('El campo CBU debe contener solo números.')

    #         if self.origin_account_cvu:
    #             if len(self.origin_account_cvu) != 22:
    #                 raise ValidationError(f'La longitud del campo CVU es incorrecta.{str(len(self.origin_account_cvu))}')
    #             if self.origin_account_cvu.isdigit():
    #                 pass
    #             else:
    #                 raise ValidationError('El campo CVU debe contener solo números.')

    #         if self.cbu_destination_account:
    #             if len(self.cbu_destination_account) != 22:
    #                 raise ValidationError(
    #                     f'La longitud del campo CBU de cuenta de destino es incorrecta.{str(len(self.cbu_destination_account))}')
    #             if self.cbu_destination_account.isdigit():
    #                 pass
    #             else:
    #                 raise ValidationError('El campo CBU de cuenta de destino debe contener solo números.')
