from odoo import fields, models, api
from datetime import datetime
import datetime as dt
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError, ValidationError


class CollectionTransaction(models.Model):
    _name = 'collection.transaction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'transaction_name'
    _order = 'id desc'

    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True, domain="[('check_origin_account','!=', True)]")
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
    amount = fields.Float(string='Monto', tracking=True, required=True,)
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
    is_commission = fields.Boolean(string='Es comisión')
    is_concilied = fields.Boolean(string='Conciliado', defualt=False, tracking=True)
    concilied_id = fields.Many2one('bank.statement', string='Conciliado con', tracking=True)
    destination_name = fields.Char(string='Cuenta Destino', compute='_get_destination_name', store=True)
    account_bank = fields.Many2one('account.bank.pagoflex', string='Cuenta Banco')
    categories = fields.Many2many('collection.category',string='Etiquetas')
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

    #Moneda
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    currency_pesos = fields.Float(string='Peso')
    currency_usd = fields.Float(string='USD')
    currency_euro = fields.Float(string='Euro')
    currency_real = fields.Float(string='Real')
    currency_crypto = fields.Float(string='Crypto')

    #MESES PREVIOS
    previous_month_pesos = fields.Float('Mes Anterior Pesos')
    previous_month_usd = fields.Float('Mes Anterior Dolares')
    previous_month_euros = fields.Float('Mes Anterior Euros')
    previous_month_reales = fields.Float('Mes Anterior Reales')

    #CHEQUE

    payment_id = fields.Many2one('account.payment')
    create_check = fields.Boolean('Ingresar cheque')

    #CAJA
    account_move_id = fields.Many2one('account.move', string='Asiento Contable')

    
    def change_positive_comission(self):
        all_comission = self.env['collection.transaction'].search([('is_commission', '=', True),('amount', '>', 0)])
        for comission in all_comission:
            comission.with_context(no_write=True).amount = comission.amount * -1
    
    def print_report(self):
        start_date = min(self.mapped('date'))
        end_date = max(self.mapped('date'))
        customer = self.customer

        domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno')]
        previous_months = self.env['collection.transaction'].search(domain)

        previous_balance = sum([pm.amount for pm in previous_months])

        previous_month_pesos = 0
        previous_month_usd = 0
        previous_month_euros = 0
        previous_month_reales = 0

        for rec in self:
            if rec.currency_id.name == "ARS":
                domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id),('currency_id', '=', rec.currency_id.id)]
                previous_months = self.env['collection.transaction'].search(domain)
                previous_month_pesos = sum([pm.amount for pm in previous_months])

            if rec.currency_id.name == "USD":
                domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id),('currency_id', '=', rec.currency_id.id)]
                previous_months = self.env['collection.transaction'].search(domain)
                previous_month_usd = sum([pm.amount for pm in previous_months])

            if rec.currency_id.name == "EUR":
                domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id),('currency_id', '=', rec.currency_id.id)]
                previous_months = self.env['collection.transaction'].search(domain)
                previous_month_euros = sum([pm.amount for pm in previous_months])

            if rec.currency_id.name == "BRL":
                domain = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', rec.customer.id),
                          ('currency_id', '=', rec.currency_id.id)]
                previous_months = self.env['collection.transaction'].search(domain)
                previous_month_reales = sum([pm.amount for pm in previous_months])


        dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', self.customer.id)], limit=1)
        dashboard_customer.update_available_balance()
        filtered_records = self

        if filtered_records:
            filtered_records[0].sudo().write({
                'previous_month': previous_balance,
                'previous_month_pesos':previous_month_pesos,
                'previous_month_usd':previous_month_usd,
                'previous_month_euros':previous_month_euros,
                'previous_month_reales':previous_month_reales,
                'available_balance': dashboard_customer.customer_available_balance,
                'start_date': start_date, 
                'end_date': end_date,
                'print_date': datetime.now(),
            })
            

            return self.env.ref('payment_collection.action_report_collection_transaction').report_action(filtered_records)
    
    def show_destination_name(self):
        all_rec = self.env['collection.transaction'].search([])
        for rec in all_rec:
            rec._get_destination_name()
            rec._get_origin_name()
            
    @api.depends('transaction_name','origin_account','origen_name_account_extern','origin_name')
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

    def break_conciliation(self):
        for rec in self:
            if rec.concilied_id:
                rec.concilied_id.concilied_id = False
                rec.concilied_id.is_concilied = False
                rec.concilied_id = False
                rec.is_concilied = False

    def write(self, vals):
        for rec in self:
            if 'amount' in vals:
                if rec.env.context.get('no_write', False):
                    continue
                if 'collection_trans_type' in vals:
                    collection_trans_type = vals['collection_trans_type']
                else:
                    collection_trans_type = rec.collection_trans_type
                if vals['amount'] < 0 and collection_trans_type == 'movimiento_recaudacion':
                    continue
                if vals['amount'] != rec.amount:
                    if rec.currency_id:
                        if rec.currency_id.name == 'ARS':
                            rec.currency_pesos = vals['amount']
                        if rec.currency_id.name == 'USD':
                            rec.currency_usd = vals['amount']
                        if rec.currency_id.name == 'EUR':
                            rec.currency_euro = vals['amount']
                        if rec.currency_id.name == 'BRL':
                            rec.currency_real = vals['amount']

                    # Relculo de comision
                    commission = ((rec.commission / 100) * vals['amount']) * -1

                    domain = [
                        ('transaction_name', '=', rec.transaction_name),
                        ('customer', '=', rec.customer.id),
                        ('is_commission', '=', True),
                        ('id', '!=', rec.id),
                    ]
                    rec_commission = self.env['collection.transaction'].search(domain)

                    if rec_commission:
                        rec_commission.currency_pesos = 0
                        rec_commission.currency_usd = 0
                        rec_commission.currency_euro = 0
                        rec_commission.currency_real = 0

                        if rec.currency_id.name == 'ARS':
                            rec_commission.currency_pesos = commission
                        if rec.currency_id.name == 'USD':
                            rec_commission.currency_usd = commission
                        if rec.currency_id.name == 'EUR':
                            rec_commission.currency_euro = commission
                        if rec.currency_id.name == 'BRL':
                            rec_commission.currency_real = commission

                        if rec_commission.account_move_id:
                            move = rec_commission.account_move_id

                            if move.state == 'posted':
                                move.button_draft()

                            amount = commission

                            move_name = rec.transaction_name + ' ' + 'Comisión'

                            account_442000 = self.env['account.account'].search([('code', '=', '442000')], limit=1)
                            account_642000 = self.env['account.account'].search([('code', '=', '642000')], limit=1)

                            if not account_442000 or not account_642000:
                                raise UserError("No se encontraron las cuentas contables 442000 o 642000.")

                            # Eliminar todas las líneas actuales del asiento
                            move.line_ids.unlink()

                            # Crear nuevas líneas
                            move.write({
                                'line_ids': [
                                    (0, 0, {
                                        'account_id': account_442000.id,
                                        'name': move_name,
                                        'debit': commission,
                                        'credit': 0.0,
                                    }),
                                    (0, 0, {
                                        'account_id': account_642000.id,
                                        'name': move_name,
                                        'debit': 0.0,
                                        'credit': commission,
                                    }),
                                ]
                            })
                            move.action_post()


                    # Recalculo de comision de agentes

                    domain = [('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id)]
                    commission_agent = self.env['collection.transaction.commission'].search(domain)
                    for agent_service in commission_agent:
                        commission_amount = (agent_service.commission_rate * vals['amount']) / 100

                        if commission_amount > 0 and rec.count == 0:
                            agent_service.sudo().write(
                                {
                                    'operation_amount': vals['amount'],
                                    'payment_rest': commission_amount,
                                    'commission_amount': commission_amount,
                                    'payment_state': 'debt',
                                }
                            )
                    rec_commission.amount = commission
                    self.recalculate_customer_balance_write(vals)

                    # modificación de asientos contables

                    if rec.account_move_id:
                        move = rec.account_move_id

                        if move.state == 'posted':
                            move.button_draft()

                        amount = float(vals.get('amount', 0.0))

                        account_442000 = self.env['account.account'].search([('code', '=', '442000')], limit=1)
                        account_642000 = self.env['account.account'].search([('code', '=', '642000')], limit=1)

                        if not account_442000 or not account_642000:
                            raise UserError("No se encontraron las cuentas contables 442000 o 642000.")

                        move.line_ids.unlink()

                        move.write({
                            'line_ids': [
                                (0, 0, {
                                    'account_id': account_442000.id,
                                    'name': rec.transaction_name,
                                    'debit': amount,
                                    'credit': 0.0,
                                }),
                                (0, 0, {
                                    'account_id': account_642000.id,
                                    'name': rec.transaction_name,
                                    'debit': 0.0,
                                    'credit': amount,
                                }),
                            ]
                        })
                        move.action_post()


            if 'commission' in vals:
                if vals['commission'] > 0:
                    rec_commission = self.env['collection.transaction'].search([('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id), ('is_commission', '=', True)])
                    if rec_commission:
                        if not rec_commission.env.context.get('no_write', False):
                            rec_commission.with_context(no_write=True).amount = ((vals['commission'] / 100) * rec.amount) * -1
                            rec_commission.with_context(no_write=True).commission = vals['commission']
                    else:
                        bills_id = self.env['product.template'].sudo().search([('name', 'ilike', 'gastos')], limit=1)
                        dict_commission_write = {
                            'amount': ((vals['commission'] / 100) * rec.amount) * -1,
                            'service': rec.service.id,
                            'customer': rec.customer.id,
                            'is_commission': True,
                            'transaction_name': rec.transaction_name,
                            'commission': vals['commission'],
                            'count': 1,
                            'collection_trans_type': 'movimiento_recaudacion',
                            'description': 'Comisión',
                            'operation': bills_id.id,
                            'currency_id': rec.currency_id.id,
                        }
                        if rec.currency_id:
                            if rec.currency_id.name == 'ARS':
                                dict_commission_write.update({'currency_pesos': ((vals['commission'] / 100) * rec.amount) * -1})
                            if rec.currency_id.name == 'USD':
                                dict_commission_write.update({'currency_usd': ((vals['commission'] / 100) * rec.amount) * -1})
                            if rec.currency_id.name == 'EUR':
                                dict_commission_write.update({'currency_euro': ((vals['commission'] / 100) * rec.amount) * -1})
                            if rec.currency_id.name == 'BRL':
                                dict_commission_write.update({'currency_real': ((vals['commission'] / 100) * rec.amount) * -1})

                        self.env['collection.transaction'].sudo().with_context(no_write=True).create(dict_commission_write)

                elif vals['commission'] == 0:
                    rec_commission = self.env['collection.transaction'].search([('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id), ('is_commission', '=', True)])
                    if rec_commission:
                        rec_commission.with_context(force_unlink=True).unlink()
            if 'date' in vals:
                if rec.env.context.get('no_write', False):
                    continue
                rec_commission = self.env['collection.transaction'].search([('transaction_name', '=', rec.transaction_name),('is_commission', '=', True)])
                agents = self.env['collection.transaction.commission'].search([('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id)])
                if agents:
                    for agent in agents:
                        agent.date = vals['date']
                if rec_commission:
                    rec_commission.with_context(no_write=True).date = vals['date']
            if 'service' in vals:
                if rec.env.context.get('no_write', False):
                    continue
                rec_commission = self.env['collection.transaction'].search([('transaction_name', '=', rec.transaction_name), ('is_commission', '=', True)])
                agents = self.env['collection.transaction.commission'].search([('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id)])
                service = self.env['collection.services.commission'].search([('id', '=', vals['service'])])
                amount = rec.amount if not 'amount' in vals else vals['amount']
                if agents:
                    for agent in agents:
                        if agent.agent.id not in service.agent_services_commission.agent.ids:
                            agent.unlink()
                            continue
                        agent.transaction_service = vals['service']
                else:
                    if service.agent_services_commission:
                        for agent_service in service.agent_services_commission:
                            commission_amount = (agent_service.commission_rate * amount) / 100
                            if commission_amount > 0 and rec.count == 0:
                                coll_trans_commi_dict = {
                                    'date': rec.date,
                                    'transaction_name': rec.transaction_name,
                                    'operation_amount': amount,
                                    'payment_rest': commission_amount,
                                    'customer': rec.customer.id,
                                    'transaction_service': vals['service'],
                                    'transaction_operation': rec.operation.id,
                                    'agent': agent_service.agent.id,
                                    'commission_rate': agent_service.commission_rate,
                                    'commission_amount': commission_amount,
                                    'currency_id': rec.currency_id.id,
                                }
                                if rec.currency_id:
                                    if rec.currency_id.name == 'ARS':
                                        coll_trans_commi_dict.update({'currency_pesos': rec.amount})
                                    if rec.currency_id.name == 'USD':
                                        coll_trans_commi_dict.update({'currency_usd': rec.amount})
                                    if rec.currency_id.name == 'EUR':
                                        coll_trans_commi_dict.update({'currency_euro': rec.amount})
                                    if rec.currency_id.name == 'BRL':
                                        coll_trans_commi_dict.update({'currency_real': rec.amount})

                                rec.env['collection.transaction.commission'].sudo().create(coll_trans_commi_dict)


                if rec_commission:
                    if 'commission' in vals:
                        rec_commission.with_context(no_write=True).commission = vals['commission']
                        rec_commission.with_context(no_write=True).amount = ((vals['commission'] / 100) * rec.amount) * -1
                    rec_commission.with_context(no_write=True).service = vals['service']

            if 'currency_id' in vals:
                if rec.env.context.get('no_write', False):
                    continue

                moneda = self.env['res.currency'].sudo().search([('id', '=', vals['currency_id'])])

                # RECAUDACION DE PAGO

                rec.with_context(no_write=True).currency_pesos = 0
                rec.with_context(no_write=True).currency_usd = 0
                rec.with_context(no_write=True).currency_euro = 0
                rec.with_context(no_write=True).currency_real = 0
                rec.with_context(no_write=True).currency_crypto = 0

                if moneda:
                    if moneda.name == 'ARS':
                        rec.with_context(no_write=True).currency_pesos = rec.amount
                    if moneda.name == 'USD':
                        rec.with_context(no_write=True).currency_usd = rec.amount
                    if moneda.name == 'EUR':
                        rec.with_context(no_write=True).currency_euro = rec.amount
                    if moneda.name == 'BRL':
                        rec.with_context(no_write=True).currency_real = rec.amount

                # COMISION DE RECAUDACION DE PAGO

                rec_commission = self.env['collection.transaction'].search(
                    [('transaction_name', '=', rec.transaction_name), ('is_commission', '=', True)])

                if rec_commission:
                    rec_commission.with_context(no_write=True).currency_id = vals['currency_id']

                    rec_commission.with_context(no_write=True).currency_pesos = 0
                    rec_commission.with_context(no_write=True).currency_usd = 0
                    rec_commission.with_context(no_write=True).currency_euro = 0
                    rec_commission.with_context(no_write=True).currency_real = 0
                    rec_commission.with_context(no_write=True).currency_crypto = 0

                    if moneda:
                        if moneda.name == 'ARS':
                            rec_commission.with_context(no_write=True).currency_pesos = rec_commission.amount
                        if moneda.name == 'USD':
                            rec_commission.with_context(no_write=True).currency_usd = rec_commission.amount
                        if moneda.name == 'EUR':
                            rec_commission.with_context(no_write=True).currency_euro = rec_commission.amount
                        if moneda.name == 'BRL':
                            rec_commission.with_context(no_write=True).currency_real = rec_commission.amount

                #COMISION POR AGENTE

                agents = self.env['collection.transaction.commission'].search(
                    [('transaction_name', '=', rec.transaction_name), ('customer', '=', rec.customer.id)])

                if agents:
                    agents.with_context(no_write=True).currency_id = vals['currency_id']

                    agents.with_context(no_write=True).currency_pesos = 0
                    agents.with_context(no_write=True).currency_usd = 0
                    agents.with_context(no_write=True).currency_euro = 0
                    agents.with_context(no_write=True).currency_real = 0
                    agents.with_context(no_write=True).currency_crypto = 0

                    if moneda:
                        if moneda.name == 'ARS':
                            agents.with_context(no_write=True).currency_pesos = agents.commission_amount
                        if moneda.name == 'USD':
                            agents.with_context(no_write=True).currency_usd = agents.commission_amount
                        if moneda.name == 'EUR':
                            agents.with_context(no_write=True).currency_euro = agents.commission_amount
                        if moneda.name == 'BRL':
                            agents.with_context(no_write=True).currency_real = agents.commission_amount



        return super().write(vals)

    def unlink(self):
        # return super().unlink() # PARA STG
        for rec in self.sorted(key=lambda r: r.amount >= 0):
            if rec.is_commission and rec.collection_trans_type == 'movimiento_recaudacion' and not self.env.context.get('force_unlink', False):
                raise UserError('No se pueden eliminar comisiones.\nAyuda: Si elimina una transacción de recaudación, su comisión tambien se eliminará.')

            domain = [
                ('transaction_name', '=', rec.transaction_name),
                ('customer', '=', rec.customer.id),
                ('is_commission', '=', True),
                ('id', '!=', rec.id),
                ('collection_trans_type', '=', 'movimiento_recaudacion'),
            ]
            rec_commission = self.env['collection.transaction'].search(domain)

            commission_ids = rec_commission.id if len(rec_commission) == 1 else rec_commission.ids

            if rec_commission and commission_ids not in self.ids:
                if rec_commission.account_move_id:
                    move = rec_commission.account_move_id

                    if move.state == 'posted':
                        move.button_draft()

                    move.line_ids.unlink()

                rec_commission.with_context(force_unlink=True).unlink()

        self.recalculate_customer_balance_unlink()

        if rec.account_move_id:
            move = rec.account_move_id

            if move.state == 'posted':
                move.button_draft()

            move.line_ids.unlink()

        return super().unlink()

    @api.model
    def create(self, vals_list):
        if vals_list['count'] == 0:

            if 'transaction_name' not in vals_list:
                vals_list['transaction_name'] = self.env['ir.sequence'].next_by_code('collection.transaction') or ('New')
            bills_id = self.env['product.template'].sudo().search([('name', 'ilike', 'gastos')], limit=1)

            #ACREDITACION

            if not vals_list['collection_trans_type'] == 'retiro' and not vals_list['collection_trans_type'] == 'movimiento_interno':
                dict_transac = {
                    'collection_trans_type': vals_list['collection_trans_type'],
                    'customer': vals_list['customer'],
                    'transaction_name': str(vals_list['transaction_name']),
                    'service': vals_list['service'],
                    'date': vals_list['date'],
                    'operation': bills_id.id,
                    'description': 'Comisión',
                    'origin_account_cuit': 0,
                    'origin_account_cvu': 0,
                    'origin_account_cbu': 0,
                    'related_customer': 0,
                    'cbu_destination_account': 0,
                    'is_commission': True,
                    'count': 1,
                    'currency_id': vals_list['currency_id'],
                 
                }
                if 'commission' not in vals_list:
                    commission_search = self.env['collection.services.commission'].sudo().search([('id', '=', vals_list['service'])], limit=1)
                    dict_transac['commission'] = commission_search.commission
                    dict_transac['amount'] = ((dict_transac['commission'] / 100) * vals_list['amount']) * -1
                else:
                    dict_transac['commission'] = vals_list['commission']
                    dict_transac['amount'] = ((vals_list['commission'] / 100) * vals_list['amount']) * -1

                if vals_list['commission'] > 0:
                    self.env['collection.transaction'].sudo().create(dict_transac)

            #RETIRO

            if vals_list['collection_trans_type'] == 'retiro' and not self.env.context.get('ignore_acr', False) and vals_list['commission'] != 0:
                dict_with = {
                    'collection_trans_type': 'movimiento_recaudacion',
                    'customer': vals_list['customer'],
                    'transaction_name': str(vals_list['transaction_name']),
                    'service': vals_list['service'],
                    'date': vals_list['date'],
                    'operation': bills_id.id,
                    'description': 'Comisión',
                    'origin_account_cuit': 0,
                    'origin_account_cvu': 0,
                    'origin_account_cbu': 0,
                    'related_customer': 0,
                    'cbu_destination_account': 0,
                    'is_commission': True,
                    'count': 1,
                    'currency_id': vals_list['currency_id'],
                }
                if 'commission' not in vals_list:
                    commission_search = self.env['collection.services.commission'].sudo().search([('id', '=', vals_list['service'])], limit=1)
                    dict_with['commission'] = commission_search.commission
                    dict_with['amount'] = ((dict_with['commission'] / 100) * vals_list['amount'])
                else:
                    dict_with['commission'] = vals_list['commission']
                    dict_with['amount'] = ((vals_list['commission'] / 100) * vals_list['amount'])
                self.env['collection.transaction'].sudo().create(dict_with)

        # ASIGNO EL MONTO AL CAMPO DE LA MONEDA CORRESPONDIENTE
        # currency_pesos
        # currency_usd
        # currency_euro
        # currency_real
        # currency_crypto

        if vals_list['currency_id']:
            moneda = self.env['res.currency'].sudo().search([('id','=', vals_list['currency_id'])])
            if moneda:
                if moneda.name == 'ARS':
                    vals_list.update({'currency_pesos':vals_list['amount']})
                if moneda.name == 'USD':
                    vals_list.update({'currency_usd':vals_list['amount']})
                if moneda.name == 'EUR':
                    vals_list.update({'currency_euro': vals_list['amount']})
                if moneda.name == 'BRL':
                    vals_list.update({'currency_real': vals_list['amount']})

        res = super(CollectionTransaction, self).create(vals_list)

        #MOVIMIENTO INTERNO

        if vals_list['collection_trans_type'] == 'movimiento_interno' and not self.env.context.get('ignore_acr', False):
            if vals_list['collection_trans_type_dest'] == 'movimiento_recaudacion':
                service_dest = self.env['collection.services.commission'].sudo().search([('id', '=', vals_list['service_dest'])])
                commission_app_amount = (vals_list['amount'] * service_dest.commission_app_rate) / 100
                dict_dest = {
                    'transaction_name': self.env['ir.sequence'].next_by_code('collection.transaction') or ('New'),
                    'customer': vals_list['customer_destination'],
                    'service': vals_list['service_dest'],
                    'commission': vals_list['commission_dest'],
                    'commission_app_rate': service_dest.commission_app_rate,
                    'commission_app_amount': commission_app_amount,
                    'date': vals_list['date'],
                    'amount': vals_list['amount'] if vals_list['amount'] > 0 else vals_list['amount'] * -1,
                    'count': 0,
                    'collection_trans_type': 'movimiento_recaudacion',
                    'currency_id': vals_list['currency_id'],
                }
                self.env['collection.transaction'].sudo().with_context(ignore_acr=True).create(dict_dest)

            elif vals_list['collection_trans_type_dest'] == 'retiro':
                dict_dest = {
                    'transaction_name': self.env['ir.sequence'].next_by_code('collection.transaction') or ('New'),
                    'customer': vals_list['customer_destination'],
                    'service': vals_list['service_dest'],
                    'commission': vals_list['commission_dest'],
                    'date': vals_list['date'],
                    'amount': vals_list['amount'] * -1 if vals_list['amount'] > 0 else vals_list['amount'],
                    'count': 0,
                    'collection_trans_type': 'retiro',
                    'currency_id': vals_list['currency_id'],
                }
                self.env['collection.transaction'].sudo().with_context(ignore_acr=True).create(dict_dest)
            else:
                pass
        message = ('Se ha creado la siguiente transaccion: %s.') % (str(vals_list['transaction_name']))
        res.message_post(body=message)

        res._create_account_move()

        return res

    #CREAR ASIENTOS CONTABLES

    def _create_account_move(self):
        self.ensure_one()
        journal_id = self.env['ir.config_parameter'].sudo().get_param('payment_collection.caja_journal_id')
        if not journal_id:
            raise UserError("No está configurado el diario de caja.")

        journal = self.env['account.journal'].browse(int(journal_id))


        cuenta_de_caja_id =  journal.profit_account_id.id
        cuenta_contraparte_id = journal.loss_account_id.id

        amount = self.amount
        if self.is_commission:
            name = self.transaction_name + ' ' + 'Comision'  or 'Movimiento de caja'
        else:
            name = self.transaction_name or 'Movimiento de caja'

        move_vals = {
            'journal_id': journal.id,
            'date': self.date or fields.Date.context_today(self),
            'ref': name,
            'currency_id':self.currency_id.id,
            'line_ids': [
                (0, 0, {
                    'account_id': cuenta_de_caja_id,
                    'debit': amount if amount > 0 else 0.0,
                    'credit': -amount if amount < 0 else 0.0,
                    'name': name,
                    'currency_id':self.currency_id.id,
                }),
                (0, 0, {
                    'account_id': cuenta_contraparte_id,
                    'debit': -amount if amount < 0 else 0.0,
                    'credit': amount if amount > 0 else 0.0,
                    'name': name,
                    'currency_id': self.currency_id.id,
                }),
            ],
        }

        move = self.env['account.move'].create(move_vals)
        move.action_post()

        self.account_move_id = move.id

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
            if not rec_customer and not rec_dashboard.manual_data:
                rec_dashboard.sudo().unlink()
            elif rec_dashboard:
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

            if collection_trans_type == 'movimiento_recaudacion':
                diff = amount_vals - self.amount
                if diff > 0:
                    rec_commission = diff - ((diff * commission) / 100)
                    commission_app_amount = diff - ((diff * commission_app_rate) / 100)
                    rec_dashboard.sudo().collection_balance += rec_commission
                    rec_dashboard.sudo().customer_real_balance += commission_app_amount
                    rec_dashboard.sudo().commission_balance += (diff * commission) / 100

                elif diff < 0:
                    rec_commission = diff - ((diff * commission) / 100)
                    commission_app_amount = diff - ((diff * commission_app_rate) / 100)
                    rec_commission *= -1
                    commission_app_amount *= -1
                    rec_dashboard.sudo().collection_balance -= rec_commission
                    rec_dashboard.sudo().customer_real_balance -= commission_app_amount
                    rec_dashboard.sudo().commission_balance -= (diff * commission) / 100

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

    @api.onchange('service_dest')
    def get_service_dest_commission(self):
        for rec in self:
            if rec.service_dest and rec.collection_trans_type_dest != 'retiro':
                rec.write({'commission_dest': rec.service_dest.commission})
            else:
                rec.write({'commission_dest': 0})

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
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
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
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
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
            if rec.customer:
                dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1)
                if dashboard_customer:
                    rec.sudo().write({'total_balance_customer': dashboard_customer.collection_balance})
                else:
                    rec.sudo().write({'total_balance_customer': 0})
            else:
                rec.sudo().write({'total_balance_customer': 0})

    @api.onchange('transaction_name')
    def get_last_client(self):
        user_id = self.env.uid
        last_client = self.env['collection.transaction'].sudo().search([('create_uid', '=', user_id)], limit=1, order='id desc')
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if last_client and not self.transaction_name and not conciliation_wiz:
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

    @api.onchange('amount')
    def calculate_commission_app_amount(self):
        self.commission_app_rate = self.service.commission_app_rate if self.service else 0
        if self.collection_trans_type != 'retiro':
            self.commission_app_amount = (self.commission_app_rate * self.amount) / 100
        elif self.collection_trans_type == 'retiro':
            self.amount = self.amount * -1 if self.amount > 0 else self.amount
    
    @api.onchange('service')
    def get_service_commission(self):
        if self.collection_trans_type == 'movimiento_recaudacion':
            self.commission = self.service.commission
        elif self.collection_trans_type == 'movimiento_interno':
            self.commission = 0
            

    @api.onchange('customer')
    def get_last_app_commission(self):
        # TRAEMOS DATOS DEL CLIENTE DESDE RES PARTNER.
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
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
                    coll_trans_commi_dict = {
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
                        'currency_id': rec.currency_id.id,
                    }
                    if rec.currency_id:
                        if rec.currency_id.name == 'ARS':
                            coll_trans_commi_dict.update({'currency_pesos': commission_amount})
                        if rec.currency_id.name == 'USD':
                            coll_trans_commi_dict.update({'currency_usd': commission_amount})
                        if rec.currency_id.name == 'EUR':
                            coll_trans_commi_dict.update({'currency_euro': commission_amount})
                        if rec.currency_id.name == 'BRL':
                            coll_trans_commi_dict.update({'currency_real': commission_amount})

                    rec.env['collection.transaction.commission'].sudo().create(coll_trans_commi_dict)

    @api.constrains('customer')
    def create_dashboard_customer(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_interno' or rec.count == 1:
                return

            dashboard_customer = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', rec.customer.id)], limit=1, order='id desc')
            if dashboard_customer:
                if rec.collection_trans_type == 'movimiento_recaudacion':
                    # Saldo Real App
                    customer_real_balance = dashboard_customer.customer_real_balance + (rec.amount - rec.commission_app_amount)

                    # Saldo Total Cliente
                    collection_balance = dashboard_customer.collection_balance + (rec.amount - ((rec.amount * rec.commission) / 100))

                    # Saldo Disponible
                    today_date = dt.datetime.now().date()
                    days_ago = dt.timedelta(days=2)
                    if rec.date <= (today_date - days_ago):
                        customer_available_balance = dashboard_customer.customer_available_balance + (rec.amount - ((rec.amount * rec.commission) / 100))
                    else:
                        customer_available_balance = dashboard_customer.customer_available_balance

                    commission_balance = dashboard_customer.commission_balance + ((rec.amount * rec.commission) / 100)

                    commission_app_amount = dashboard_customer.commission_app_amount + rec.commission_app_amount

                    # caclulo promedio de comision
                    domain_customer = [('customer', '=', rec.customer.id), ('collection_trans_type', '!=', 'movimiento_interno')]
                    customer = self.env['collection.transaction'].sudo().search(domain_customer)
                    commission_app_rate_list = [c.commission_app_rate for c in customer if not c.is_commission]
                    no_commission_app_amount_list = [c.amount for c in customer if not c.is_commission]
                    if no_commission_app_amount_list:
                        commission_app_rate = sum(commission_app_rate_list) / len(no_commission_app_amount_list)
                    else:
                        commission_app_rate = sum(commission_app_rate_list)

                    dashboard_customer.sudo().write(
                        {
                            'customer': rec.customer.id,
                            'last_operation_date': datetime.now(),
                            'customer_real_balance': customer_real_balance,
                            'customer_available_balance': customer_available_balance,
                            'collection_balance': collection_balance,
                            'commission_balance': commission_balance,
                            'commission_app_amount': commission_app_amount,
                            'commission_app_rate': commission_app_rate,
                        }
                    )
                elif rec.collection_trans_type == 'retiro':
                    if rec.commission > 0:
                        commission_wd = ((rec.amount * rec.commission) / 100) * -1
                    else:
                        commission_wd = 0

                    total_commission_balance = dashboard_customer.commission_balance - commission_wd

                    # Saldo Real App
                    total_customer_real_balance = dashboard_customer.customer_real_balance + rec.amount + commission_wd

                    # Saldo Disponible
                    total_customer_available_balance = dashboard_customer.customer_available_balance + rec.amount

                    # Saldo Total Cliente
                    total_collection_balance = dashboard_customer.collection_balance + rec.amount

                    dashboard_customer.sudo().write(
                        {
                            'customer': rec.customer.id,
                            'last_operation_date': datetime.now(),
                            'customer_real_balance': total_customer_real_balance,  # SALDO REAL APP
                            'customer_available_balance': total_customer_available_balance,  # SALDO DISPONIBLE CLIENTE
                            'collection_balance': total_collection_balance,  # SALDO TOTAL CLIENTE
                            'commission_balance': total_commission_balance,
                        }
                    )

            else:
                if rec.commission > 0 and rec.collection_trans_type == 'retiro':
                    commission_retiro = ((rec.amount * rec.commission) / 100) * -1
                    total_customer_real_balance = rec.amount + commission_retiro
                    total_collection_balance = rec.amount
                    customer_available_balance = rec.amount

                elif rec.commission == 0 and rec.collection_trans_type == 'retiro':
                    total_collection_balance = rec.amount
                    customer_available_balance = rec.amount
                    total_customer_real_balance = rec.amount

                else:  # Sino es movimiento recaudacion
                    total_collection_balance = rec.amount - ((rec.amount * rec.commission) / 100)

                    today_date = dt.datetime.now().date()
                    days_ago = dt.timedelta(days=2)
                    if rec.date <= (today_date - days_ago):
                        customer_available_balance = rec.amount - ((rec.amount * rec.commission) / 100)
                    else:
                        customer_available_balance = 0

                    # Saldo Real App
                    total_customer_real_balance = rec.amount - rec.commission_app_amount

                self.env['collection.dashboard.customer'].sudo().create(
                    {
                        'customer': rec.customer.id,
                        'customer_real_balance': total_customer_real_balance,  # SALDO REAL APP
                        'customer_available_balance': customer_available_balance,  # SALDO DISPONIBLE
                        'collection_balance': total_collection_balance,  # SALDO TOTAL CLIENTE
                        'last_operation_date': datetime.now(),
                        'commission_balance': ((rec.amount * rec.commission) / 100),
                        'commission_app_amount': rec.commission_app_amount,
                        'commission_app_rate': rec.commission_app_rate,
                        'manual_data': False,
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

    @api.onchange('amount')
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
                rec.commission_app_amount = 0
            else:
                rec.commission = rec.service.commission

    @api.onchange('origin_account')
    def get_origin_account_data(self):
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
        for rec in self:
            self.sudo().write(
                {
                    'origin_account_cuit': rec.origin_account.cuit,
                    'origin_account_cbu': rec.origin_account.cbu,
                    'origin_account_cvu': rec.origin_account.cvu,
                    'alias_origen': rec.origin_account.alias,
                }
            )

    @api.onchange('collection_trans_type', 'service')
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
                services = rec.service.search([('services', '=', rec.service.services.id), ('name_account', '!=', False)])
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

    @api.onchange('collection_trans_type')
    def set_empty_fields(self):
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
        for rec in self:
            rec.write(
                {
                    'destination_account': False,
                    'customer_origin': False,
                    'origin_account': False,
                    'customer_destination': False,
                    'service_dest': False,
                    'origen_name_account_extern': False,
                    'origin_account_cuit': False,
                    'origin_account_cbu': False,
                    'origin_account_cvu': False,
                    'alias_origen': False,
                }
            )

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

    def approved(self):
        self.transaction_state = 'aprobado'

    def pending(self):
        self.transaction_state = 'pendiente'

    def refused(self):
        self.transaction_state = 'rechazado'

    def intern(self):
        self.transaction_state = 'interno'

    # def print_report_xls(self):
    #     list_dict_total = []
    #     if self.nombre:
    #         for rec in self.totales_ids:
    #             print(rec)
    #             dict_totales_id = {'moneda': rec.moneda, 'capital': rec.capital, 'intereses': rec.intereses, 'gastos': rec.gastos, 'impuestos': rec.impuestos, 'cuota_total': rec.cuota_total}
    #             list_dict_total.append(dict_totales_id)

    #         list_dict_dif = []
    #         data = {}

    #         return self.env.ref('loans_scoring.report_prestamo_bancario_xlsx_id').report_action(self, data)

    @api.model
    def open_filter_collection_movement_wiz(self, data):
        return {
            'name': 'Filtrar Movimientos',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'filter.collection.movement',
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


    def open_create_check(self):
        search_journal = self.env['journal.transaction'].sudo().search([('id', '=', '1')])
        diario = False
        method = False
        if not search_journal:
            raise ValidationError('Diario de cheques no configurado.')
        if search_journal:
            diario = search_journal.journal_id.id
            method = search_journal.journal_id.inbound_payment_method_line_ids.filtered(
                lambda m: m.code == 'new_third_party_checks')
            if not method:
                raise ValidationError('No se encontro el metodo de pago: Nuevo Cheque de Tercero')


        return {
            'name': 'Ingresar cheque',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'account.payment',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_journal_id': diario,
                        'default_payment_method_line_id': method.id,
                        'default_amount': self.amount,
                        'default_currency_id': self.currency_id.id,
                        'default_date': self.date,
                        'default_partner_id': self.customer.id,
                        'default_check_origin_collection': True,
                        'default_id_transaction':self.id,
                        },
        }
