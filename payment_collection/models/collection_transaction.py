from odoo import fields, models, api, _
from datetime import datetime, timedelta
import datetime as dt
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo.exceptions import ValidationError

class CollectionTransaction(models.Model):
    _name = 'collection.transaction'
    _inherit=['mail.thread', 'mail.activity.mixin']
    _rec_name = 'transaction_name'
    _order = 'id desc'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,)
    transaction_name = fields.Char(string='N° Transacción', tracking=True,)
    service = fields.Many2one('product.template', string='Servicio', required=True, tracking=True, domain=[('collection_type', '=', 'service')])
    commission = fields.Float(string='Comisión', required=True,)
    operation = fields.Many2one(
        'product.template', relation='operation', string='Operación', required=True, tracking=True, domain=[('collection_type', '=', 'operation')]
    )
    date = fields.Date(string='Fecha', tracking=True, default=datetime.now())
    description = fields.Text(string='Descripción', tracking=True,)
    origin_account_cuit = fields.Char(string='CUIT de cuenta de origen', tracking=True, required=True, default=False)
    origin_account_cvu = fields.Char(string='CVU de cuenta de origen', tracking=True,)
    origin_account_cbu = fields.Char(string='CBU de cuenta de origen', tracking=True,)
    related_customer = fields.Char(string='Cliente Relacionado', tracking=True)
    amount = fields.Float(string='Monto', tracking=True, required=True)
    date_available_amount = fields.Date('Fecha del monto disponible')
    real_balance = fields.Float(string='Saldo Real')
    available_balance = fields.Float(string='Saldo Disponible', tracking=True,)
    cbu_destination_account = fields.Char(string='CBU de cuenta de destino', tracking=True, default=False)
    name_destination_account = fields.Char(string='Nombre de cuenta de destino', tracking=True,)
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True,)
    commission_app_amount = fields.Float(string='Monto de la App', tracking=True,)
    cbu_check = fields.Char('Check cbu')
    previous_month = fields.Float('Mes Anterior', compute='compute_previous_month')
    count = fields.Integer('', default=0)
    
    
    @api.onchange('amount')
    def calculate_commission_app_amount(self):
        self.commission_app_amount = (self.commission_app_rate * self.amount) / 100
    
    @api.onchange('customer')
    def get_last_app_commission(self):
        last_app_commission = self.env['commission.app'].search([], order='date desc', limit=1)
        self.commission_app_rate = last_app_commission.commission_rate
        
    @api.onchange('service')
    def get_commission_service(self):
        if self.service:
            service = self.env['collection.services.commission'].search(
                [('services', '=', self.service.id), ('customer', '=', self.customer.id)], limit=1, order='id desc')
            if service:
                self.commission = service.commission
            else:
                self.commission = 0

    @api.model
    def create(self, vals):
        if vals['count'] == 0:
            vals['transaction_name'] = self.env['ir.sequence'].next_by_code('collection.transaction') or ('New')
            dict_transac = {'customer': vals['customer'],
                            'transaction_name': str(vals['transaction_name']),
                            'service': vals['service'],
                            'date': vals['date'],
                            'commission': vals['commission'],
                            'operation': vals['operation'],
                            'description': 'Comisión',
                            'amount': ((vals['commission'] / 100) * vals['amount']) * -1,
                            'origin_account_cuit': 0,
                            'origin_account_cvu': 0,
                            'origin_account_cbu': 0,
                            'related_customer': 0,
                            'cbu_destination_account': 0,
                            'count': 1,
                            }
            self.env['collection.transaction'].sudo().create(dict_transac)


        res = super(CollectionTransaction, self).create(vals)

        message = ("Se ha creado la siguiente transaccion: %s.") % (str(vals['transaction_name']))

        res.message_post(body=message)

        return res

    def _compute_account_move(self):
        pass

    @api.constrains('customer')
    def compute_commission_agent(self):
        self.ensure_one()

        service = self.env['collection.services.commission'].search([('services', '=', self.service.id),('customer','=', self.customer.id)], limit=1, order='id desc')
        for agent_service in service.agent_services_commission:
            commission_amount = (agent_service.commission_rate * self.amount) / 100
            if commission_amount > 0 and self.count == 0:
                self.env['collection.transaction.commission'].sudo().create(
                    {
                        'date': self.date,
                        'transaction_name': self.transaction_name,
                        'operation_amount': self.amount,
                        'payment_rest': commission_amount,
                        'customer': self.customer.id,
                        'transaction_service': self.service.id,
                        'transaction_operation': self.operation.id,
                        'agent': agent_service.agent.id,
                        'commission_rate': agent_service.commission_rate,
                        'commission_amount': commission_amount,
                    }
                )

    def _compute_generate_expense(self):
        pass

    @api.constrains('customer')
    def create_dashboard_customer(self):
        self.ensure_one()
        customer = self.env['collection.transaction'].sudo().search([('customer', '=', self.customer.id)])
        real_balance_list = [c.amount for c in customer]
        available_balance_list = [c.available_balance for c in customer]
        commission_balance_list = [c.amount for c in customer if c.amount < 0]
        commission_app_rate_list = [c.commission_app_rate for c in customer]
        commission_app_amount_list = [c.commission_app_amount for c in customer]
        if customer:
            real_balance = sum(real_balance_list)
            available_balance = sum(available_balance_list)
            commission_balance = sum(commission_balance_list)
            commission_app_rate = sum(commission_app_rate_list) / len(commission_app_rate_list)
            commission_app_amount = sum(commission_app_amount_list)
        else:
            real_balance = self.real_balance
            available_balance = self.available_balance
            if self.commission < 0:
                commission_balance = self.commission
            else:
                commission_balance = 0

        dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', self.customer.id)], limit=1, order='id desc')

        if dashboard_customer:
            dashboard_customer.sudo().write(
                {
                    'customer': self.customer.id,
                    'customer_real_balance': real_balance,
                    'customer_available_balance': available_balance,
                    'last_operation_date': datetime.now(),
                    'commission_balance': commission_balance,
                    'collection_balance': dashboard_customer.collection_balance + self.amount if self.amount > 0 else dashboard_customer.collection_balance,
                    'commission_app_amount': ((dashboard_customer.collection_balance + self.amount) * commission_app_rate) / 100,
                    'commission_app_rate': commission_app_rate
                }
            )

        else:
            self.env['collection.dashboard.customer'].sudo().create(
                {
                    'customer': self.customer.id,
                    'customer_real_balance': real_balance,
                    'customer_available_balance': available_balance,
                    'last_operation_date': datetime.now(),
                    'commission_balance': commission_balance,
                    'collection_balance': self.amount if self.amount > 0 else 0 ,
                    'commission_app_amount': self.commission_app_amount,
                    'commission_app_rate': self.commission_app_rate
                }
            )

    @api.onchange('customer', 'amount')
    @api.constrains('amount')
    def _compute_real_balance_costumer(self):
        for rec in self:
            if self.customer:
                domain = [('customer', '=', self.customer.id)]
                payments = self.env['collection.transaction'].sudo().search(domain)
                total_real_balance = sum([pay.amount for pay in payments])
                rec.real_balance = total_real_balance


    @api.onchange('customer', 'date')
    def _compute_available_balance_costumer(self):
        for rec in self:
            if self.customer:
                timedelta= dt.timedelta(days=2)

                domain = [('customer', '=', self.customer.id),('date', '<=', rec.date - timedelta)]
                payments = self.env['collection.transaction'].sudo().search(domain)
                available_balance = sum([pay.amount for pay in payments])
                rec.available_balance = available_balance
                rec.date_available_amount =  rec.date - timedelta

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

            domain = [('date', '>=', start_date), ('date', '<=', end_date),('customer','=',rec.customer.id)]

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
                        rec.origin_account_cuit = rec.origin_account_cuit.replace('-','').replace(' ','')

                    if len(rec.origin_account_cuit) > 11 or len(rec.origin_account_cuit) < 11:
                        raise ValidationError(F'La longitud del campo CUIT es incorrecta.{len(rec.origin_account_cuit)}')


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