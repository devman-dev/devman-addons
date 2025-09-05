from odoo import fields, models, api
from datetime import datetime
import datetime as dt
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class CollecTransWiz(models.TransientModel):
    _name = 'collec.trans.wiz'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,
                               domain="[('check_origin_account','!=', True)]")
    transaction_name = fields.Char(string='N° Transacción', tracking=True)
    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    commission = fields.Float(string='Comisión (%)', digits=(16, 3))
    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)
    date = fields.Date(string='Fecha', tracking=True, default=datetime.now())
    description = fields.Text(string='Descripción', tracking=True)
    origin_account_cuit = fields.Char(string='CUIT origen', tracking=True, default=False)
    origin_account_cvu = fields.Char(string='CVU origen', tracking=True)
    origin_account_cbu = fields.Char(string='CBU origen', tracking=True)
    origen_name_account_extern = fields.Char(string='Cuenta Origen')
    related_customer = fields.Char(string='Cliente Relacionado', tracking=True)
    amount = fields.Float(string='Monto', tracking=True, required=True, )
    date_available_amount = fields.Date('Fecha del monto disponible')
    real_balance = fields.Float(string='Saldo Real App', compute='compute_real_balance_costumer')
    available_balance = fields.Float(string='Saldo Disponible Cliente', compute='compute_available_balance')
    total_balance_customer = fields.Float(string='Saldo Total Cliente', compute='get_total_balance_customer')
    cuit_destination_account = fields.Char('CUIT Destino')
    cbu_destination_account = fields.Char(string='CBU Destino', tracking=True, default=False)
    cvu_destination_account = fields.Char(string='CVU Destino', tracking=True, default=False)
    name_destination_account = fields.Char(string='Cuenta Destino', tracking=True)
    commission_app_rate = fields.Float(string='Comisión de la App (%)', tracking=True, digits=(16, 3))
    commission_app_amount = fields.Float(string='Monto de la App', tracking=True)
    previous_month = fields.Float('Mes Anterior')
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
    customer_destination = fields.Many2one('res.partner', string='Cliente Destino',
                                           domain="[('check_origin_account','!=', True)]")
    destination_account = fields.Many2one('collection.services.commission', string='Cuenta Destino')
    customer_origin = fields.Many2one('res.partner', string='Cliente Origen',
                                      domain="[('check_origin_account','!=', True)]")
    origin_type = fields.Selection([('externo', 'Externo'), ('interno', 'Interno')], default='externo',
                                   string='Tipo de Origen')
    origin_account_table = fields.Many2many('collection.services.commission')
    collection_trans_type_dest = fields.Selection(
        [('movimiento_recaudacion', 'Acreditación'), ('retiro', 'Mov. Retiro')],
        default='movimiento_recaudacion',
        string='Tipo de Transacción',
    )
    service_dest = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)
    commission_dest = fields.Float(string='Comisión (%)')
    is_commission = fields.Boolean(string='Es comisión')
    is_concilied = fields.Boolean(string='Conciliado', defualt=False, tracking=True)
    concilied_id = fields.Many2one('bank.statement', string='Conciliado con', tracking=True)
    destination_name = fields.Char(string='Cuenta Destino', compute='_get_destination_name', store=True)
    account_bank = fields.Many2one('account.bank.pagoflex', string='Cuenta Banco')
    # categories = fields.Many2many('collection.category', string='Etiquetas')
    categories = fields.Many2many(
        comodel_name='collection.category',
        relation='wiz_categories_rel',
        column1='wiz_id',
        column2='category_id',
        string='Etiquetas'
    )
    check_number = fields.Char(string='Nro del cheque')
    check_date = fields.Date(string='Fecha del cheque')
    check_deposit_date = fields.Date(string='Fecha de depósito')
    check_endorsement = fields.Char(string='Endoso')
    check_bank = fields.Many2one('account.bank.pagoflex', string='Banco del cheque')
    origin_name = fields.Char(string='Cuenta Origen', compute='_get_origin_name', store=True)

    # Campos para el reporte
    start_date = fields.Date(string='Fecha inicio para el reporte')
    end_date = fields.Date(string='Fecha fin para el reporte')
    print_date = fields.Date(string='Fecha de impresión')

    # Moneda
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    currency_pesos = fields.Float(string='Peso')
    currency_usd = fields.Float(string='USD')
    currency_euro = fields.Float(string='Euro')
    currency_real = fields.Float(string='Real')
    currency_crypto = fields.Float(string='Crypto')

    # MESES PREVIOS
    previous_month_pesos = fields.Float('Mes Anterior Pesos')
    previous_month_usd = fields.Float('Mes Anterior Dolares')
    previous_month_euros = fields.Float('Mes Anterior Euros')
    previous_month_reales = fields.Float('Mes Anterior Reales')

    # CHEQUE

    payment_id = fields.Many2one('account.payment')
    create_check = fields.Boolean('Ingresar cheque')

    # CAJA
    account_move_id = fields.Many2one('account.move', string='Asiento Contable')

    @api.depends('transaction_name', 'origin_account', 'origen_name_account_extern', 'origin_name')
    def _get_origin_name(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_recaudacion':
                if rec.origin_type == 'externo':
                    rec.origin_name = rec.origen_name_account_extern
                else:
                    rec.origin_name = rec.origin_account.name_account
            elif rec.collection_trans_type == 'retiro' or rec.collection_trans_type == 'movimiento_interno':
                rec.origin_name = rec.origin_account.name_account

    @api.depends('transaction_name', 'destination_account', 'destination_name')
    def _get_destination_name(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_recaudacion' or rec.collection_trans_type == 'movimiento_interno':
                rec.destination_name = rec.destination_account.name_account
            elif rec.collection_trans_type == 'retiro':
                if rec.origin_type == 'externo':
                    rec.destination_name = rec.name_destination_account
                else:
                    rec.destination_name = rec.destination_account.name_account

    @api.depends('customer', 'real_balance')
    def compute_real_balance_costumer(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search(
                    [('customer', '=', rec.customer.id)], limit=1)
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
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search(
                    [('customer', '=', rec.customer.id)], limit=1)
                if dashboard_customer:
                    rec.sudo().write({'available_balance': dashboard_customer.customer_available_balance})
                else:
                    rec.sudo().write({'available_balance': 0})
            else:
                rec.sudo().write({'available_balance': 0})

    @api.depends('customer', 'amount')
    def get_total_balance_customer(self):
        for rec in self:
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search(
                    [('customer', '=', rec.customer.id)], limit=1)
                if dashboard_customer:
                    rec.sudo().write({'total_balance_customer': dashboard_customer.collection_balance})
                else:
                    rec.sudo().write({'total_balance_customer': 0})
            else:
                rec.sudo().write({'total_balance_customer': 0})



    def create_collection_transaction(self):
        self.ensure_one()

        self.payment_id.mark_as_sent()

        self.payment_id.conciliado = 'conciliado'

        movimiento = {
            'customer': self.customer.id if self.customer else False,
            'transaction_name': self.transaction_name,
            'service': self.service.id if self.service else False,
            'commission': self.commission,
            'operation': self.operation.id if self.operation else False,
            'date': self.date,
            'description': self.description,
            'origin_account_cuit': self.origin_account_cuit,
            'origin_account_cvu': self.origin_account_cvu,
            'origin_account_cbu': self.origin_account_cbu,
            'origen_name_account_extern': self.origen_name_account_extern,
            'related_customer': self.related_customer,
            'amount': self.amount,
            'cuit_destination_account': self.cuit_destination_account,
            'cbu_destination_account': self.cbu_destination_account,
            'cvu_destination_account': self.cvu_destination_account,
            'name_destination_account': self.name_destination_account,
            'commission_app_rate': self.commission_app_rate,
            'commission_app_amount': self.commission_app_amount,
            'count': self.count,
            'alias_destination_account': self.alias_destination_account,
            'alias_origen': self.alias_origen,
            'transaction_state': self.transaction_state,
            'collection_trans_type': self.collection_trans_type,
            'withdrawal_operations': [(6, 0, self.withdrawal_operations.ids)] if self.withdrawal_operations else [],
            'alert_withdrawal': self.alert_withdrawal,
            'internal_notes': self.internal_notes,
            'origin_account': self.origin_account.id if self.origin_account else False,
            'customer_destination': self.customer_destination.id if self.customer_destination else False,
            'destination_account': self.destination_account.id if self.destination_account else False,
            'customer_origin': self.customer_origin.id if self.customer_origin else False,
            'origin_type': self.origin_type,
            'origin_account_table': [(6, 0, self.origin_account_table.ids)] if self.origin_account_table else [],
            'collection_trans_type_dest': self.collection_trans_type_dest,
            'service_dest': self.service_dest.id if self.service_dest else False,
            'commission_dest': self.commission_dest,
            'is_commission': self.is_commission,
            'is_concilied': self.is_concilied,
            'concilied_id': self.concilied_id.id if self.concilied_id else False,
            'destination_name': self.destination_name,
            'account_bank': self.account_bank.id if self.account_bank else False,
            'categories': [(6, 0, self.categories.ids)] if self.categories else [],
            'check_number': self.check_number,
            'check_date': self.check_date,
            'check_deposit_date': self.check_deposit_date,
            'check_endorsement': self.check_endorsement,
            'check_bank': self.check_bank.id if self.check_bank else False,
            'origin_name': self.origin_name,
            'currency_id': self.currency_id.id if self.currency_id else False,
            'payment_id': self.payment_id.id if self.payment_id else False,
            'account_move_id': self.account_move_id.id if self.account_move_id else False,
            # Campos de reporte
            'start_date': self.start_date,
            'end_date': self.end_date,
            'print_date': self.print_date,
            # Monedas
            'currency_pesos': self.currency_pesos,
            'currency_usd': self.currency_usd,
            'currency_euro': self.currency_euro,
            'currency_real': self.currency_real,
            'currency_crypto': self.currency_crypto,
            # Meses previos
            'previous_month': self.previous_month,
            'previous_month_pesos': self.previous_month_pesos,
            'previous_month_usd': self.previous_month_usd,
            'previous_month_euros': self.previous_month_euros,
            'previous_month_reales': self.previous_month_reales,
            # Cheque
            'create_check': self.create_check,
        }
        self.env['collection.transaction'].sudo().create(movimiento)

