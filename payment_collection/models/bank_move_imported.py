from odoo import fields, models, api
from odoo.exceptions import UserError

import base64
import io
import pandas as pd
import math

class BankMoveImported(models.Model):
    _name = 'bank.move.imported'
    _description = 'Bank Move Imported'
    _rec_name = 'customer_id'

    customer_id = fields.Many2one('res.partner', string='Cliente', required=True)
    date = fields.Date(string='Fecha', required=True)
    bank_id = fields.Many2one('account.bank.pagoflex', string='Banco', required=True)
    file = fields.Binary(string='Archivo', required=True)
    comment = fields.Text(string='Comentario')
    amount = fields.Char(string='Columna Monto', required=True)
    origin_account = fields.Char(string='Columna Cuenta Origen')
    origin_cuit = fields.Char(string='Columna Cuit Origen')
    origin_cvu = fields.Char(string='Columna Cvu Origen')
    bank_commission_entry = fields.Float(string='Comisión del banco por ingreso (%)')
    bank_commission_egress = fields.Float(string='Comisión del banco por egreso (%)')
    service_id = fields.Many2one('collection.services.commission', string='Servicio', required=True)
    commission = fields.Float(string='Comisión (%)', digits=(16, 3))
    app_commission = fields.Float(string='Comisión de la App(%)', digits=(16, 3))
    operation_id = fields.Many2one('product.template', relation='operation', string='Operación')
    destination_account_id = fields.Many2one('collection.services.commission', string='Cuenta Destino')
    withdrawal_operations = fields.Many2many('product.template', domain=[('collection_type', '=', 'operation')])
    collection_trans_type = fields.Selection(
        [('movimiento_recaudacion', 'Acreditación'), ('retiro', 'Mov. Retiro')],
        default='movimiento_recaudacion',
        string='Tipo de Transacción',
    )
    cuit_destination_account = fields.Char('CUIT Destino')
    cbu_destination_account = fields.Char(string='CBU Destino', tracking=True, default=False)
    cvu_destination_account = fields.Char(string='CVU Destino', tracking=True, default=False)
    alias_destination_account = fields.Char(string='Alias Destino')
    
    @api.onchange('customer_id')
    def _blank_service(self):
        self.service_id = False

    @api.onchange('bank_commission_egress', 'bank_commission_entry')
    def check_bank_commission(self):
        if self.bank_commission_egress and self.bank_commission_entry:
            raise UserError('No puede tener comisión de ingreso y egreso al mismo tiempo')

    @api.onchange('destination_account_id')
    def get_destination_account_data(self):
        conciliation_wiz = self.env.context.get('conciliation_wiz', False)
        if conciliation_wiz:
            return
        if self.destination_account_id:
            self.sudo().write(
                {
                    'cuit_destination_account': self.destination_account_id.cuit,
                    'cbu_destination_account': self.destination_account_id.cbu,
                    'cvu_destination_account': self.destination_account_id.cvu,
                    'alias_destination_account': self.destination_account_id.alias,
                }
            )
        else:
            self.sudo().write(
                {
                    'cuit_destination_account': '',
                    'cbu_destination_account': '',
                    'cvu_destination_account': '',
                    'alias_destination_account': '',
                }
            )

    @api.onchange('service_id')
    def get_service_commission(self):
        if self.service_id:
            self.commission = self.service_id.commission
            self.app_commission = self.service_id.commission_app_rate
        else:
            self.commission = 0
            self.app_commission = 0

    @api.onchange('collection_trans_type', 'service')
    def set_default_operation(self):
        for rec in self:
            if rec.collection_trans_type == 'movimiento_recaudacion':
                accreditation = rec.operation_id.search([('check_accreditation', '=', True), ('collection_type', '=', 'operation')])
                if accreditation:
                    rec.withdrawal_operations = accreditation.ids
                else:
                    rec.withdrawal_operations = accreditation

            elif rec.collection_trans_type == 'retiro':
                extraction = rec.operation_id.search([('check_withdrawal', '=', True), ('collection_type', '=', 'operation')])
                services = rec.service_id.search([('services', '=', rec.service_id.services.id), ('name_account', '!=', False)])
                if extraction:
                    rec.withdrawal_operations = extraction.ids
                else:
                    rec.withdrawal_operations = extraction
                if services:
                    rec.origin_account_table = services.ids

            # elif rec.collection_trans_type == 'movimiento_interno':
            #     internal = rec.operation_id.search([('check_internal', '=', True), ('collection_type', '=', 'operation')])
            #     if internal:
            #         rec.withdrawal_operations = internal.ids
            #     else:
            #         rec.withdrawal_operations = internal

    def execute_bank_file(self):
        self.ensure_one()
        collection_transaction = self.env['collection.transaction']
        bank_statement = self.env['bank.statement']
        try:
            file_content = base64.b64decode(self.file)
            excel_file = io.BytesIO(file_content)
        except Exception as e:
            raise UserError('Error al leer el archivo: %s' % e)
        excel_data = pd.read_excel(excel_file)

        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
        letter = self.amount.upper()
        l_index = letters.index(letter)
        col_amount_name = excel_data.columns[l_index]
        amounts = excel_data[col_amount_name].tolist()

        origin_account = False
        origin_cuit = False
        origin_cvu = False

        if self.origin_account:
            origin_account_letter = self.origin_account.upper()
            l_index_origin_account = letters.index(origin_account_letter)
            col_origin_account_name = excel_data.columns[l_index_origin_account]
            origin_account = excel_data[col_origin_account_name].tolist()

        if self.origin_cuit:
            origin_cuit_letter = self.origin_cuit.upper()
            l_index_origin_cuit = letters.index(origin_cuit_letter)
            col_origin_cuit_name = excel_data.columns[l_index_origin_cuit]
            origin_cuit = excel_data[col_origin_cuit_name].tolist()

        if self.origin_cvu:
            origin_letter = self.origin_cvu.upper()
            l_index_origin = letters.index(origin_letter)
            col_origin_name = excel_data.columns[l_index_origin]
            origin_cvu = excel_data[col_origin_name].tolist()

        count = 0
        for amount in amounts:
            if not isinstance(origin_cvu[count], str) and not isinstance(origin_account[count], str) and not isinstance(origin_cuit[count], str):
                if math.isnan(origin_cvu[count]) and math.isnan(origin_account[count]) and math.isnan(origin_cuit[count]):
                    count += 1
                    break
            try:
                customer_exits = collection_transaction.search(
                    [
                        ('customer', '=', self.customer_id.id),
                        ('collection_trans_type', '=', self.collection_trans_type),
                        ('origin_account_cvu', '=', origin_cvu[count].replace('"', '') if origin_cvu else False),
                        ('origin_account_cuit', '=', origin_cuit[count].replace('"', '') if origin_cuit else False),
                        ('origen_name_account_extern', '=', origin_account[count] if origin_account else False),
                        ('amount', '=', amount),
                    ]
                )
                if customer_exits:
                    count += 1
                    continue

                if self.collection_trans_type == 'retiro':
                    amount = abs(amount) * -1

                transaction_id = collection_transaction.create(
                    {
                        'collection_trans_type': self.collection_trans_type,
                        'customer': self.customer_id.id,
                        'date': self.date,
                        'amount': amount,
                        'origin_account_cuit': origin_cuit[count].replace('"', '') if origin_cuit else False,
                        'origin_account_cvu': origin_cvu[count].replace('"', '') if origin_cvu else False,
                        'origen_name_account_extern': origin_account[count] if origin_account else False,
                        'description': self.comment,
                        'service': self.service_id.id,
                        'commission': self.commission,
                        'commission_app_rate': self.app_commission,
                        'operation': self.operation_id.id,
                        'destination_account': self.destination_account_id.id,
                        'is_concilied': True,
                        'count': 0,
                        'account_bank': self.bank_id.id,
                    }
                )

                statement_id = bank_statement.create(
                    {
                        'date': self.date,
                        'amount': amount,
                        'titular': origin_account[count] if origin_account else False,
                        'cuit': origin_cuit[count].replace('"', '') if origin_cuit else False,
                        'cvu': origin_cvu[count].replace('"', '') if origin_cvu else False,
                        'bank_commission_entry': self.bank_commission_entry,
                        'bank_commission_egress': self.bank_commission_egress,
                        'concilied_id': transaction_id.id,
                        'is_concilied': True,
                        'bank_statement_id': self.bank_id.id,
                    }
                )
                transaction_id.write({'concilied_id': statement_id.id})
                commission = 0
                if self.bank_commission_entry:
                    commission = amount * self.bank_commission_entry / 100
                    comment = 'Comisión del Banco por Ingreso'

                if self.bank_commission_egress:
                    commission = amount * self.bank_commission_egress / 100
                    comment = 'Comisión del Banco por Egreso'

                if commission:
                    bank_statement.create(
                        {
                            'date': self.date,
                            'amount': abs(commission) * -1,
                            'titular': origin_account[count] if origin_account else False,
                            'cuit': origin_cuit[count].replace('"', '') if origin_cuit else False,
                            'cvu': origin_cvu[count].replace('"', '') if origin_cvu else False,
                            'bank_commission_entry': self.bank_commission_entry,
                            'bank_commission_egress': self.bank_commission_egress,
                            'concilied_id': transaction_id.id,
                            'is_concilied': True,
                            'bank_statement_id': self.bank_id.id,
                            'reference': comment,
                        }
                    )
                count += 1
            except Exception as e:
                raise UserError('Error al crear los registros: %s' % e)
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            'simple_notification',
            {
                'type': 'success',
                'message': 'Operación realizada con éxito',
            },
        )
