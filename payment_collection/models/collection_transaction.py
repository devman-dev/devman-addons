from odoo import fields, models, api
from datetime import datetime
import datetime as dt
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError


class CollectionTransaction(models.Model):
    _name = 'collection.transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'transaction_name'
    _order = 'id desc'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True, domain="[('check_origin_account','!=', True)]")
    transaction_name = fields.Char(string='N° Transacción', tracking=True)
    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    commission = fields.Float(string='Comisión (%)')
    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)
    date = fields.Date(string='Fecha', tracking=True, default=datetime.now())
    description = fields.Text(string='Descripción', tracking=True)
    origin_account_cuit = fields.Char(string='CUIT origen', tracking=True, default=False)
    origin_account_cvu = fields.Char(string='CVU origen', tracking=True)
    origin_account_cbu = fields.Char(string='CBU origen', tracking=True)
    origen_name_account_extern = fields.Char(string='Cuenta Origen')
    related_customer = fields.Char(string='Cliente Relacionado', tracking=True)
    amount = fields.Float(string='Monto', tracking=True, required=True)
    date_available_amount = fields.Date('Fecha del monto disponible')
    real_balance = fields.Float(string='Saldo Real App', compute='compute_real_balance_costumer')
    available_balance = fields.Float(string='Saldo Disponible Cliente', tracking=True, compute='compute_available_balance')
    total_balance_customer = fields.Float(string='Saldo Total Cliente', compute='get_total_balance_customer', tracking=True)
    cuit_destination_account = fields.Char('CUIT Destino')
    cbu_destination_account = fields.Char(string='CBU Destino', tracking=True, default=False)
    cvu_destination_account = fields.Char(string='CVU Destino', tracking=True, default=False)
    name_destination_account = fields.Char(string='Cuenta Destino', tracking=True)
    commission_app_rate = fields.Float(string='Comisión de la App', tracking=True)
    commission_app_amount = fields.Float(string='Monto de la App', tracking=True)
    previous_month = fields.Float('Mes Anterior', compute='compute_previous_month')
    count = fields.Integer('', default=0)
    alias_destination_account = fields.Char(string='Alias Destino')
    alias_origen = fields.Char(string='Alias Origen')
    transaction_state = fields.Selection(
        [
            ('aprobado', 'Aprobado'),
            ('pendiente', 'Pendiente'),
            ('rechazado', 'Rechazado'),
            ('interno', 'Interno'),
        ],
        string='Estado',
        default='aprobado',
    )
    collection_trans_type = fields.Selection(
        [('movimiento_recaudacion', 'Acreditación'), ('retiro', 'Mov. Retiro'), ('movimiento_interno', 'Mov. Interno')],
        default='movimiento_recaudacion',
        string='Tipo de Transacción',
    )
    withdrawal_operations = fields.Many2many('product.template', domain=[('collection_type', '=', 'operation')])
    alert_withdrawal = fields.Boolean()
    internal_notes = fields.Text()
    origin_account = fields.Many2one('collection.services.commission', string='Cuenta Origen')
    customer_destination = fields.Many2one('res.partner', string='Cliente Destino', domain="[('check_origin_account','!=', True)]")
    destination_account = fields.Many2one('collection.services.commission', string='Cuenta Destino')
    customer_origin = fields.Many2one('res.partner', string='Cliente Origen', domain="[('check_origin_account','!=', True)]")
    origin_type = fields.Selection([('externo', 'Externo'), ('interno', 'Interno')], default='externo', string='Tipo de Origen')
    origin_account_table = fields.Many2many('collection.services.commission')
    collection_trans_type_dest = fields.Selection(
        [('movimiento_recaudacion', 'Acreditación'), ('retiro', 'Mov. Retiro')],
        default='movimiento_recaudacion',
        string='Tipo de Transacción',
    )
    service_dest = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    commission_dest = fields.Float(string='Comisión (%)')

    def write(self, values):
        # return super().write(values) # PARA STG
        for rec in self:
            if 'amount' in values:
                if 'collection_trans_type' in values:
                    collection_trans_type = values['collection_trans_type']
                else:
                    collection_trans_type = rec.collection_trans_type
                if values['amount'] < 0 and collection_trans_type == 'movimiento_recaudacion':
                    continue
                if values['amount'] != rec.amount:
                    # Relculo de comision
                    commission = ((rec.commission / 100) * values['amount']) * -1

                    domain = [
                        ('transaction_name', '=', rec.transaction_name),
                        ('customer', '=', rec.customer.id),
                        ('amount', '<', 0),
                        ('id', '!=', rec.id),
                    ]
                    rec_commission = self.env['collection.transaction'].search(domain)

                    # Relculo de comision de agentes

                    domain = [('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id)]
                    commission_agent = self.env['collection.transaction.commission'].search(domain)
                    for agent_service in commission_agent:
                        commission_amount = (agent_service.commission_rate * values['amount']) / 100
                        if commission_amount > 0 and rec.count == 0:
                            result = agent_service.payment_amount - agent_service.payment_rest
                            agent_service.sudo().write(
                                {
                                    'operation_amount': values['amount'],
                                    'payment_rest': result,
                                    'commission_amount': commission_amount,
                                    'payment_state': 'debt',
                                }
                            )
                    rec_commission.amount = commission
                    self.recalculate_customer_balance_write(values)
        return super().write(values)

    def unlink(self):
        # return super().unlink() # PARA STG
        for rec in self.sorted(key=lambda r: r.amount >= 0):
            if rec.amount < 0 and rec.collection_trans_type == 'movimiento_recaudacion' and not self.env.context.get('force_unlink', False):
                raise UserError('No se pueden eliminar comisiones.\nAyuda: Si elimina una transacción de recaudación, su comisión tambien se eliminará.')

            domain = [
                ('transaction_name', '=', rec.transaction_name),
                ('customer', '=', rec.customer.id),
                ('amount', '<', 0),
                ('id', '!=', rec.id),
                ('collection_trans_type', '=', 'movimiento_recaudacion'),
            ]
            rec_commission = self.env['collection.transaction'].search(domain)

            commission_ids = rec_commission.id if len(rec_commission) == 1 else rec_commission.ids

            if rec_commission and commission_ids not in self.ids:
                rec_commission.with_context(force_unlink=True).unlink()

        self.recalculate_customer_balance_unlink()

        return super().unlink()

    @api.model
    def create(self, vals):
        if vals['count'] == 0:
            if 'transaction_name' not in vals:
                vals['transaction_name'] = self.env['ir.sequence'].next_by_code('collection.transaction') or ('New')
            bills_id = self.env['product.template'].sudo().search([('name', 'ilike', 'gastos')], limit=1)

            if not vals['collection_trans_type'] == 'retiro' and not vals['collection_trans_type'] == 'movimiento_interno':
                dict_transac = {
                    'collection_trans_type': vals['collection_trans_type'],
                    'customer': vals['customer'],
                    'transaction_name': str(vals['transaction_name']),
                    'service': vals['service'],
                    'date': vals['date'],
                    'operation': bills_id.id,
                    'description': 'Comisión',
                    'origin_account_cuit': 0,
                    'origin_account_cvu': 0,
                    'origin_account_cbu': 0,
                    'related_customer': 0,
                    'cbu_destination_account': 0,
                    'count': 1,
                }
                if 'commission' not in vals:
                    commission_search = self.env['collection.services.commission'].sudo().search([('id', '=', vals['service'])], limit=1)
                    dict_transac['commission'] = commission_search.commission
                    dict_transac['amount'] = ((dict_transac['commission'] / 100) * vals['amount']) * -1
                else:
                    dict_transac['commission'] = vals['commission']
                    dict_transac['amount'] = ((vals['commission'] / 100) * vals['amount']) * -1
                self.env['collection.transaction'].sudo().create(dict_transac)

        res = super(CollectionTransaction, self).create(vals)

        if vals['collection_trans_type'] == 'movimiento_interno' and not self.env.context.get('ignore_acr', False):
            if vals['collection_trans_type_dest'] == 'movimiento_recaudacion':
                service_dest = self.env['collection.services.commission'].sudo().search([('id', '=', vals['service_dest'])])
                commission_app_amount = (vals['amount'] * service_dest.commission_app_rate) / 100
                dict_dest = {
                    'transaction_name': self.env['ir.sequence'].next_by_code('collection.transaction') or ('New'),
                    'customer': vals['customer_destination'],
                    'service': vals['service_dest'],
                    'commission': vals['commission_dest'],
                    'commission_app_rate': service_dest.commission_app_rate,
                    'commission_app_amount': commission_app_amount,
                    'date': vals['date'],
                    'amount': vals['amount'] if vals['amount'] > 0 else vals['amount'] *-1,
                    'count': 0,
                    'collection_trans_type': 'movimiento_recaudacion',
                }
                self.env['collection.transaction'].sudo().with_context(ignore_acr=True).create(dict_dest)

            elif vals['collection_trans_type_dest'] == 'retiro':
                dict_dest = {
                    'transaction_name': self.env['ir.sequence'].next_by_code('collection.transaction') or ('New'),
                    'customer': vals['customer_destination'],
                    'service': vals['service_dest'],
                    'commission': vals['commission_dest'],
                    'date': vals['date'],
                    'amount': vals['amount'] * -1 if vals['amount'] > 0 else vals['amount'],
                    'count': 0,
                    'collection_trans_type': 'retiro',
                }
                self.env['collection.transaction'].sudo().with_context(ignore_acr=True).create(dict_dest)
            else:
                pass
        message = ('Se ha creado la siguiente transaccion: %s.') % (str(vals['transaction_name']))
        res.message_post(body=message)

        return res

    @api.model
    def recalculate_total_recs(self):
        group = self.env.ref('payment_collection.groups_payment_collection_admin')
        if not group.id in self.env.user.groups_id.ids:
            raise UserError('Esta función solo puede ser ejecutada por usuarios con permiso de administrador.')
        all_recs = self.env['res.partner'].sudo().search([('check_origin_account', '=', False)])
        for rec in all_recs:
            today_date = dt.datetime.now().date()
            days_ago = dt.timedelta(days=2)
            total_available = self.env['collection.transaction'].sudo().search([('customer', '=', rec.id),('date', '<=', today_date - days_ago),('collection_trans_type', '!=', 'movimiento_interno'),])
            total_recaudation = self.env['collection.transaction'].sudo().search([('customer', '=', rec.id), ('collection_trans_type', '=', 'movimiento_recaudacion')])
            total_withdrawal = self.env['collection.transaction'].sudo().search([('customer', '=', rec.id), ('collection_trans_type', '=', 'retiro')])
            dashboard = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.id)])
            if not total_recaudation and not total_withdrawal:
                continue
            
            if dashboard:
                dashboard.sudo().write(
                    {
                        'customer_real_balance': 0,
                        'customer_available_balance': 0,
                        'collection_balance': 0,
                        'commission_balance': 0,
                        'commission_app_rate': 0,
                        'commission_app_amount': 0,
                    }
                )
            total_amount_recau = sum([c.amount for c in total_recaudation])
            total_amount_withdr = sum([c.amount for c in total_withdrawal])
            total_amount_available = sum([c.amount for c in total_available])
            total_amount_app = sum([c.commission_app_amount for c in total_recaudation])
            total_amount_recau_no_commi =  [c.amount for c in total_recaudation if c.amount > 0]
            total_app_rate = sum([c.commission_app_rate for c in total_recaudation]) / len(total_amount_recau_no_commi)
            total_commi_amount = sum([c.amount for c in total_recaudation if c.amount < 0])
            dashboard.sudo().write(
                {
                    'customer_real_balance': (total_amount_recau + (total_commi_amount * -1)) - total_amount_app,
                    'customer_available_balance': total_amount_available,
                    'collection_balance': total_amount_recau,
                    'commission_balance': total_commi_amount,
                    'commission_app_rate': total_app_rate,
                    'commission_app_amount': total_amount_app,
                }
            )

    def recalculate_customer_balance_unlink(self):
        for rec in self:
            rec_customer = self.env['collection.transaction'].search([('customer', '=', rec.customer.id), ('id', 'not in', self.ids), ('amount', '>', 0)])
            rec_dashboard = self.env['collection.dashboard.customer'].search([('customer', '=', rec.customer.id)])
            rec_service_id = rec.service.id
            agent_domain = [
                ('transaction_service', '=', rec_service_id),
                ('transaction_name', '=', rec.transaction_name),
                ('customer', '=', rec.customer.id),
            ]
            rec_agent_trans = self.env['collection.transaction.commission'].search(agent_domain)
            for agent in rec_agent_trans:
                agent.unlink()
            if not rec_customer:
                rec_dashboard.sudo().unlink()
            elif rec_customer and rec_dashboard:
                if rec.collection_trans_type == 'movimiento_recaudacion':
                    if rec.amount < 0:
                        continue
                    rec_amount = rec.amount - ((rec.amount * rec.commission) / 100)
                    rec_amount_app = rec.amount - ((rec.amount * rec.commission_app_rate) / 100)
                    available_balance = rec_dashboard.customer_available_balance

                    if available_balance > 0:
                        available_balance -= rec_amount
                    total_balance = rec_dashboard.collection_balance - rec_amount
                    real_balance_app = rec_dashboard.customer_real_balance - rec_amount_app
                    rec_dashboard.sudo().write({'collection_balance': total_balance, 'customer_real_balance': real_balance_app})
                else:
                    amount = rec.amount * -1
                    rec_amount_app = amount
                    available_balance = rec_dashboard.customer_available_balance
                    available_balance += amount
                    total_balance = rec_dashboard.collection_balance + amount
                    real_balance_app = rec_dashboard.customer_real_balance + rec_amount_app
                    rec_dashboard.sudo().write(
                        {
                            'collection_balance': total_balance,
                            'customer_real_balance': real_balance_app,
                            'customer_available_balance': available_balance,
                        }
                    )

    def recalculate_customer_balance_write(self, vals):
        if 'amount' in vals:
            customer_id = vals['customer'] if 'customer' in vals else self.customer.id
            rec_dashboard = self.env['collection.dashboard.customer'].search([('customer', '=', customer_id)])
            amount_vals = vals['amount']
            collection_trans_type = vals['collection_trans_type'] if 'collection_trans_type' in vals else self.collection_trans_type
            commission = vals['commission'] if 'commission' in vals else self.commission
            commission_app_rate = vals['commission_app_rate'] if 'commission_app_rate' in vals else self.commission_app_rate

            date = vals['date'] if 'date' in vals else self.date

            today_date = dt.datetime.now().date()
            days_ago = dt.timedelta(days=2)

            if collection_trans_type == 'movimiento_recaudacion':
                diff = amount_vals - self.amount
                if diff > 0:
                    rec_commission = diff - ((diff * commission) / 100)
                    commission_app_amount = diff - ((diff * commission_app_rate) / 100)
                    rec_dashboard.sudo().collection_balance += rec_commission
                    rec_dashboard.sudo().customer_real_balance += commission_app_amount
                    if date <= today_date - days_ago:
                        rec_dashboard.sudo().customer_available_balance += diff

                elif diff < 0:
                    rec_commission = diff - ((diff * commission) / 100)
                    commission_app_amount = diff - ((diff * commission_app_rate) / 100)
                    rec_commission *= -1
                    commission_app_amount *= -1
                    rec_dashboard.sudo().collection_balance -= rec_commission
                    rec_dashboard.sudo().customer_real_balance -= commission_app_amount
                    if date <= today_date - days_ago:
                        diff *= -1
                        rec_dashboard.sudo().customer_available_balance -= diff

            elif collection_trans_type == 'retiro':
                diff = (amount_vals - self.amount) * -1
                if diff > 0:
                    rec_dashboard.sudo().collection_balance -= diff
                    rec_dashboard.sudo().customer_real_balance -= diff
                    rec_dashboard.sudo().customer_available_balance -= diff
                elif diff < 0:
                    diff *= -1
                    rec_dashboard.sudo().collection_balance += diff
                    rec_dashboard.sudo().customer_real_balance += diff
                    rec_dashboard.sudo().customer_available_balance += diff
        else:
            pass

    @api.onchange('service_dest')
    def get_service_dest_commission(self):
        for rec in self:
            if rec.service_dest and rec.collection_trans_type_dest != 'retiro':
                rec.write({'commission_dest': rec.service_dest.commission})

    @api.onchange('collection_trans_type_dest')
    def empty_commission_dest(self):
        for rec in self:
            if rec.collection_trans_type_dest == 'retiro':
                rec.write({'commission_dest': 0})
            else:
                rec.write({'commission_dest': rec.service_dest.commission})

    @api.constrains('amount')
    def check_amount(self):
        for rec in self:
            if rec.amount == 0 and rec.count != 1:
                raise UserError('No puedes guardar un registro sin monto.')

    @api.onchange('customer_origin', 'origin_type')
    def empty_origin_fields(self):
        if self.collection_trans_type == 'movimiento_recaudacion':
            self.sudo().write(
                {
                    'customer_origin': '' if self.origin_type == 'externo' else self.customer_origin,
                    'origin_account': '',
                    'origin_account_cuit': '',
                    'origin_account_cbu': '',
                    'origin_account_cvu': '',
                    'alias_origen': '',
                }
            )
        elif self.collection_trans_type == 'retiro':
            self.sudo().write(
                {
                    'destination_account': '',
                    'cuit_destination_account': '',
                    'cbu_destination_account': '',
                    'cvu_destination_account': '',
                    'alias_destination_account': '',
                }
            )

    @api.onchange('destination_account')
    def get_destination_account_data(self):
        if self.destination_account:
            self.sudo().write(
                {
                    'cuit_destination_account': self.destination_account.cuit,
                    'cbu_destination_account': self.destination_account.cbu,
                    'cvu_destination_account': self.destination_account.cvu,
                    'alias_destination_account': self.destination_account.alias,
                }
            )
        else:
            self.sudo().write(
                {
                    'cuit_destination_account': '',
                    'cbu_destination_account': '',
                    'cvu_destination_account': '',
                    'alias_destination_account': '',
                    'name_destination_account': '',
                }
            )

    @api.depends('customer', 'amount')
    def get_total_balance_customer(self):
        for rec in self:
            customer = rec.env['collection.transaction'].sudo().search([('customer', '=', rec.customer.id), ('collection_trans_type', '!=', 'movimiento_interno')])
            total_balance = sum([r.amount for r in customer])
            rec.sudo().write({'total_balance_customer': total_balance})

    @api.onchange('transaction_name')
    def get_last_client(self):
        user_id = self.env.uid
        last_client = self.env['collection.transaction'].sudo().search([('create_uid', '=', user_id)], limit=1, order='id desc')
        if last_client and not self.transaction_name:
            self.sudo().write(
                {
                    'customer': last_client.customer.id,
                    'service': last_client.service.id,
                    'name_destination_account': last_client.service.name_account,
                    'cuit_destination_account': last_client.service.cuit,
                    'cbu_destination_account': last_client.service.cbu,
                    'cvu_destination_account': last_client.service.cvu,
                    'alias_destination_account': last_client.service.alias,
                }
            )

    @api.onchange('amount', 'service')
    def calculate_commission_app_amount(self):
        self.commission_app_rate = self.service.commission_app_rate if self.service else 0
        if self.collection_trans_type != 'retiro':
            self.commission_app_amount = (self.commission_app_rate * self.amount) / 100
        elif self.collection_trans_type == 'retiro':
            self.amount = self.amount * -1 if self.amount > 0 else self.amount

    @api.onchange('customer')
    def get_last_app_commission(self):
        # TRAEMOS DATOS DEL CLIENTE DESDE RES PARTNER.
        if self.customer:
            self.sudo().write(
                {
                    'cbu_destination_account': '',
                    'cvu_destination_account': '',
                    'alias_destination_account': '',
                    'name_destination_account': '',
                    'destination_account': '',
                    'service': False,
                    'internal_notes': self.customer.comment,
                }
            )
        if not self.service:
            self.sudo().write(
                {
                    'cbu_destination_account': '',
                    'cvu_destination_account': '',
                    'alias_destination_account': '',
                    'name_destination_account': '',
                    'destination_account': '',
                    'internal_notes': self.customer.comment,
                    'origin_account_cuit': '',
                    'origin_account_cbu': '',
                    'origin_account_cvu': '',
                    'alias_origen': '',
                    'origin_account': '',
                    'customer_origin': '',
                }
            )

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

    @api.constrains('customer')
    def create_dashboard_customer(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_interno' or rec.count == 1:
                return
            today_date = dt.datetime.now().date()
            days_ago = dt.timedelta(days=2)
            domain_balance = [
                ('customer', '=', rec.customer.id),
                ('date', '<=', today_date - days_ago),
                ('collection_trans_type', '!=', 'movimiento_interno'),
            ]
            domain_withdrawal = [('customer', '=', rec.customer.id), ('collection_trans_type', '=', 'retiro')]
            domain_customer = [('customer', '=', rec.customer.id), ('collection_trans_type', '!=', 'movimiento_interno')]

            customer = self.env['collection.transaction'].sudo().search(domain_customer)
            available_balance_ids = self.env['collection.transaction'].sudo().search(domain_balance)
            avaiable_withdrawal_ids = self.env['collection.transaction'].sudo().search(domain_withdrawal)
            available_balance_list = [a.amount for a in available_balance_ids]
            available_withdrawal_list = [a.amount for a in avaiable_withdrawal_ids if a.id == rec.id]
            real_balance_list = [c.amount if c.count != 1 else 0 for c in customer]
            commission_app_rate_list = [c.commission_app_rate for c in customer]
            commission_balance_list = [c.amount for c in customer if c.amount < 0 and c.collection_trans_type == 'movimiento_recaudacion']
            commission_app_amount_list = [c.commission_app_amount for c in customer]
            no_commission_app_amount_list = [c.amount for c in customer if c.amount > 0]

            if customer:
                real_balance = sum(real_balance_list)
                withdrawal_balance = sum(available_withdrawal_list) * -1
                available_balance = sum(available_balance_list)
                commission_balance = sum(commission_balance_list)
                if no_commission_app_amount_list:
                    commission_app_rate = sum(commission_app_rate_list) / len(no_commission_app_amount_list)
                else:
                    commission_app_rate = sum(commission_app_rate_list)
                commission_app_amount = sum(commission_app_amount_list)
            else:
                real_balance = rec.real_balance
                available_balance = rec.available_balance
                if rec.commission < 0:
                    commission_balance = rec.commission
                else:
                    commission_balance = 0

            dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1, order='id desc')
            if dashboard_customer:
                dashboard_customer.customer_available_balance = 0
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
                        'customer_available_balance': available_balance,
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

    @api.depends('customer', 'real_balance')
    def compute_real_balance_costumer(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1)
                if dashboard_customer:
                    rec.sudo().write({'real_balance': dashboard_customer.customer_real_balance})
                else:
                    rec.sudo().write({'real_balance': 0})
            else:
                rec.real_balance = 0

    @api.depends('customer', 'amount')
    def compute_available_balance(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1)
                if dashboard_customer:
                    rec.sudo().write({'available_balance': dashboard_customer.customer_available_balance})
                else:
                    rec.sudo().write({'available_balance': 0})
            else:
                rec.sudo().write({'available_balance': 0})

    @api.onchange('amount', 'date', 'customer')
    def _calculate_amount_withdrawal(self):
        for rec in self:
            if rec.customer and rec.collection_trans_type == 'retiro':
                amount = 0
                if rec.amount > 0:
                    amount = rec.amount
                else:
                    amount = rec.amount * -1

                if amount > rec.available_balance:
                    rec.alert_withdrawal = True

    @api.constrains('amount')
    def disable_alert_withdrawal(self):
        for rec in self:
            if rec.collection_trans_type == 'retiro' and rec.alert_withdrawal:
                rec.alert_withdrawal = False

    @api.depends('date')
    def compute_previous_month(self):
        for rec in self:
            days = rec.date.day - 1
            start_date = rec.date - relativedelta(months=1, days=days)
            end_date = rec.date - relativedelta(days=days) - relativedelta(days=1)

            domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id)]

            previous_months = self.env['collection.transaction'].search(domain)
            rec.previous_month = sum([pm.amount for pm in previous_months])

    @api.onchange('collection_trans_type')
    def no_commission_on_withdrawal(self):
        for rec in self:
            if rec.collection_trans_type == 'retiro' or rec.collection_trans_type == 'movimiento_interno':
                rec.commission = 0
            else:
                rec.commission = rec.service.commission

    @api.onchange('origin_account')
    def get_origin_account_data(self):
        for rec in self:
            self.sudo().write(
                {
                    'origin_account_cuit': rec.origin_account.cuit,
                    'origin_account_cbu': rec.origin_account.cbu,
                    'origin_account_cvu': rec.origin_account.cvu,
                    'alias_origen': rec.origin_account.alias,
                }
            )

    @api.onchange('collection_trans_type')
    def set_default_operation(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_recaudacion':
                accreditation = rec.operation.search([('check_accreditation', '=', True), ('collection_type', '=', 'operation')])
                if accreditation:
                    rec.withdrawal_operations = accreditation.ids
                else:
                    rec.withdrawal_operations = accreditation

                self.amount = self.amount * -1 if self.amount < 0 else self.amount
                self.alert_withdrawal = False
            elif rec.collection_trans_type == 'retiro':
                extraction = rec.operation.search([('check_withdrawal', '=', True), ('collection_type', '=', 'operation')])
                services = rec.service.search([('services', '=', rec.service.services.id)])
                if extraction:
                    rec.withdrawal_operations = extraction.ids
                else:
                    rec.withdrawal_operations = extraction
                if services:
                    rec.origin_account_table = services.ids

                self.amount = self.amount * -1 if self.amount > 0 else self.amount

            elif rec.collection_trans_type == 'movimiento_interno':
                self.alert_withdrawal = False
                internal = rec.operation.search([('check_internal', '=', True), ('collection_type', '=', 'operation')])
                if internal:
                    rec.withdrawal_operations = internal.ids
                else:
                    rec.withdrawal_operations = internal

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
