from odoo import fields, api, models
from datetime import datetime
from odoo.exceptions import ValidationError
import gspread
from oauth2client.service_account import ServiceAccountCredentials


class TransferRequest(models.Model):
    _name = 'transfer.request'
    _order = 'id desc'


    customer = fields.Many2one('res.partner', string='Cliente', required=True, tracking=True,
                               domain="[('check_origin_account','!=', True)]")

    service = fields.Many2one('collection.services.commission', string='Servicio', tracking=True)

    commission = fields.Float(string='Comisión (%)', digits=(16, 3))

    operation = fields.Many2one('product.template', relation='operation', string='Operación', tracking=True)

    date = fields.Date(string='Fecha', tracking=True, default=datetime.now())

    description = fields.Text(string='Descripción', tracking=True)

    amount = fields.Float(string='Monto', tracking=True, required=True, )

    origin_account_cuit = fields.Char(string='CUIT origen', tracking=True, default=False)
    origin_account_cvu = fields.Char(string='CVU origen', tracking=True)
    origin_account_cbu = fields.Char(string='CBU origen', tracking=True)
    origen_name_account_extern = fields.Char(string='Cuenta Origen')

    cuit_destination_account = fields.Char('CUIT Destino')
    cbu_destination_account = fields.Char(string='CBU Destino', tracking=True, default=False)
    cvu_destination_account = fields.Char(string='CVU Destino', tracking=True, default=False)

    name_destination_account = fields.Char(string='Cuenta Destino', tracking=True)

    alias_destination_account = fields.Char(string='Alias Destino')
    alias_origen = fields.Char(string='Alias Origen')

    origin_account = fields.Many2one('collection.services.commission', string='Cuenta Origen')

    origin_account_table = fields.Many2many('collection.services.commission')


    account_bank = fields.Many2one('account.bank.pagoflex', string='Cuenta Banco')

    transfer_request_state = fields.Selection([('nuevo', 'Nuevo'), ('pasado','Pasado'), ('revisar', 'Revisar'), ('cancelado','Cancelado'),], default='nuevo', string='Estado')

    withdrawal_operations = fields.Many2many('product.template', domain=[('collection_type', '=', 'operation')])

    transfer_type = fields.Selection([('retiro', 'Retiro'), ('transferencia', 'Transferencia')], string='Tipo de Transferencia')



    @api.onchange('service')
    def set_default_operation(self):
        for rec in self:
            extraction = rec.operation.search([('check_withdrawal', '=', True), ('collection_type', '=', 'operation')])
            services = rec.service.search([('services', '=', rec.service.services.id), ('name_account', '!=', False)])
            if extraction:
                rec.withdrawal_operations = extraction.ids
            else:
                rec.withdrawal_operations = extraction
            if services:
                rec.origin_account_table = services.ids


    def transfer_movements_to_collection(self):
        list_transfers = []
        for rec in self:
            if rec.transfer_type == 'transferencia' or not rec.transfer_type:
                if not rec.service or not rec.operation or not rec.origin_account:
                    msg = f"""No se puede pasar el pedido de transferencia, complete los campos faltantes.\n {'Servicio.' if not rec.service else ''} {'Operación.' if not rec.operation else ''} {'Cuenta Origen.' if not rec.origin_account else ''}"""
                    raise  ValidationError(msg)
            elif rec.transfer_type == 'retiro':
                if not rec.service or not rec.operation:
                    raise  ValidationError(f'No se puede pasar el pedido de retiro, complete los campos faltantes.\n {"" if rec.service else "Servicio."} {"" if rec.operation else "Operación."}')


            if rec.transfer_request_state == 'nuevo':
                dict_data = {
                'count': 0,
                'collection_trans_type':'retiro',
                'date': rec.date,
                'customer': rec.customer.id,
                'service': rec.service.id,
                'commission': rec.commission,
                'withdrawal_operations': rec.withdrawal_operations.ids,
                'operation': rec.operation.id,
                'description': rec.description,
                'amount': abs(rec.amount)*-1,
                'account_bank': rec.account_bank.id,
                'origin_account_table': rec.origin_account_table.ids,
                'origin_account': rec.origin_account.id,
                'origin_account_cuit': rec.origin_account.cuit,
                'origin_account_cvu': rec.origin_account.cvu,
                'origin_account_cbu': rec.origin_account.cbu,
                'alias_origen': rec.origin_account.alias,


                'name_destination_account': rec.name_destination_account,
                'alias_destination_account': rec.alias_destination_account,
                'cbu_destination_account': rec.cbu_destination_account,
                'cvu_destination_account': rec.cvu_destination_account,
                }
                list_transfers.append(dict_data)
                rec.transfer_request_state = 'pasado'

                # Exportar a Google Sheets
                # Define el alcance
                scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                # Carga las credenciales
                creds = ServiceAccountCredentials.from_json_keyfile_name('/mnt/extra-addons/source/devman-addons/payment_collection/keypagoflex.json', scope)
                client = gspread.authorize(creds)
                # Abre la hoja de cálculo
                spreadsheet = client.open("test")
                # Selecciona la hoja por nombre
                sheet = spreadsheet.worksheet("Hoja 1")
                # Datos a escribir
                new_row = [rec.name_destination_account,
                            rec.alias_destination_account,
                            abs(rec.amount)*-1,
                            rec.cbu_destination_account or rec.cvu_destination_account,
                            ]
                # Agrega una nueva fila al final de la hoja
                sheet.append_row(new_row)




        if list_transfers:
            self.env['collection.transaction'].sudo().create(list_transfers)

            self.env['bus.bus']._sendone(self.env.user.partner_id, 'simple_notification', {
                'type': 'success',
                'message': "Operación realizada con éxito.",
            })