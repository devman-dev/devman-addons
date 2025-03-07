from odoo.http import request, Controller, route, content_disposition
import requests
import json
import xlsxwriter
from io import BytesIO
import logging
_logger = logging.getLogger(__name__)

class WebFormWalletController(Controller):

    @route('/wallet', auth='user', website=True)
    def web_form_wallet(self, **kwargs):
        collection_balance = request.env['collection.dashboard.customer'].sudo().recalculate_total_recs(request.env.user.partner_id.id)
        customer_balance = collection_balance if collection_balance else 0.00

        transactions = request.env['collection.transaction'].sudo().search([('customer', '=', request.env.user.partner_id.id), ('collection_trans_type', '!=', 'movimiento_interno')], order='id desc', limit=10)

        grouped_transactions = {}
        for transaction in transactions:
            if transaction.service:
                service = transaction.service.id
            else:
                continue
            if service not in grouped_transactions:
                grouped_transactions[service] = []
            grouped_transactions[service].append(transaction.amount)

        for key in grouped_transactions.keys():
            grouped_transactions[key] = sum(grouped_transactions[key])

        return request.render('billetera_pagoflex.web_template_wallet', {'customer_balance': customer_balance, 'transactions': transactions, 'user_name': request.env.user.name, 'grouped_transactions': grouped_transactions})

    @route('/wallet/transfer/accounts', auth='user', website=True, methods=['GET'])
    def web_form_transfer(self, **kwargs):
        response = [
            {
                'id': '1',
                'cbu': '1234567890112345678901',
                'cvu': '1234567890112345678901',
                'alias': 'alias.demo',
                'name_account': 'Datos Demostracion',
            },
            {
                'id': '2',
                'cbu': '1234567890112345678901',
                'cvu': '1234567890112345678901',
                'alias': 'alias.demo2',
                'name_account': 'Datos Demostracion2',
            },
        ]
        return request.render('billetera_pagoflex.web_form_template_transfer', {'list_accounts': response})

    @route('/wallet/transfer/accounts/new_account', auth='user', website=True, methods=['GET'])
    def web_form_transfer_new_account(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_new_account')

    @route('/wallet/transfer/accounts/confirm_account', auth='user', website=True, methods=['GET'])
    def web_form_transfer_confirm_account(self, **kwargs):
        account = {
            'id': '2',
            'cbu': '1234567890112345678901',
            'cvu': '1234567890112345678901',
            'alias': 'alias.demo2',
            'name_account': 'Datos Demostracion2',
            'cuit': '12345678901',
        }
        return request.render('billetera_pagoflex.web_form_template_transfer_confirm_account', {'account': account})

    @route('/bank/get_data', type='http', auth='public', methods=['GET'])
    def bank_get_data(self, **datos):
        dict_data = [
            {
                'id': '1',
                'cbu': '1234567890112345678901',
                'cvu': '1234567890112345678901',
                'alias': 'alias.demo',
                'name_account': 'Datos Demostracion',
            },
            {
                'id': '2',
                'cbu': '1234567890112345678901',
                'cvu': '1234567890112345678901',
                'alias': 'alias.demo2',
                'name_account': 'Datos Demostracion2',
            },
        ]
        return request.make_response(json.dumps(dict_data), headers=[('Content-Type', 'application/json')])

    @route('/wallet/transfer/account/<int:account_id>', auth='user', website=True)
    def transfer_account(self, account_id, **kwargs):
        account = {
            'id': '2',
            'cbu': '1234567890112345678901',
            'cvu': '1234567890112345678901',
            'alias': 'alias.demo2',
            'name_account': 'Datos Demostracion2',
        }
        collection_balance = request.env['collection.dashboard.customer'].sudo().recalculate_total_recs(request.env.user.partner_id.id)
        customer_balance = collection_balance if collection_balance else 0.00
        return request.render('billetera_pagoflex.transfer_account_template', {'account': account, 'customer_balance': customer_balance})

    @route('/wallet/transfer/account/revision/<int:account_id>', auth='user', website=True)
    def revision_account(self, account_id, **kwargs):
        account = {
            'id': '2',
            'cbu': '1234567890112345678901',
            'cvu': '1234567890112345678901',
            'alias': 'alias.demo2',
            'name_account': 'Datos Demostracion2',
            'cuit': '12345678901',
        }
        return request.render('billetera_pagoflex.web_form_template_transfer_account_revision', {'account': account, 'amount': 100})

    @route('/wallet/transfer/sended', auth='user', website=True)
    def transfer_sended(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_sended')

    @route('/wallet/movements/<string:mov_type>/<int:id_service>/<int:page>', auth='user', website=True, methods=['GET'])
    def show_movements(self, mov_type, id_service, page=1, **kwargs):
        items_per_page = 10

        domain = [('customer', '=', request.env.user.partner_id.id), ('service', '=', id_service)]
        # if mov_type == 'pending':
        #     domain.append(('transaction_state', '=', 'pendiente'))
        # elif mov_type == 'refused':
        #     domain.append(('transaction_state', '=', 'rechazado'))
        # elif mov_type == 'approved':
        #     domain.append(('transaction_state', '=', 'aprobado'))

        all_transactions = request.env['collection.transaction'].sudo().search(domain)

        total_items = len(all_transactions)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        transactions = all_transactions[start_index:end_index]

        # Calcular las páginas visibles
        visible_pages = []
        if total_pages > 1:
            visible_pages = [1]  # Siempre mostrar la primera página
            if page > 4:
                visible_pages.append('...')

            for i in range(max(2, page - 2), min(total_pages, page + 3) + 1):
                visible_pages.append(i)

            if page < total_pages - 3:
                visible_pages.append('...')

            if total_pages not in visible_pages:
                visible_pages.append(total_pages)

        # Obtener el balance del cliente
        customer = request.env['collection.dashboard.customer'].sudo().search([('customer', '=', request.env.user.partner_id.id)])
        customer_balance = customer.collection_balance if customer else 0.00

        return request.render(
            'billetera_pagoflex.web_template_movements',
            {
                'transactions': transactions,
                'current_page': page,
                'total_pages': total_pages,
                'visible_pages': visible_pages,
                'mov_type': mov_type,
                'customer_balance': customer_balance,
                'id_service': id_service,
            },
        )

    @route('/wallet/transfer_request', auth='user', website=True)
    def send_transfer_request(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_request_transfer')

    @route('/wallet/tranfers_request/<string:mov_type>/<int:page>', auth='user', website=True)
    def show_movements_request(self, mov_type, page=1, **kwargs):
        items_per_page = 10

        domain = [('customer', '=', request.env.user.partner_id.id)]
        # if mov_type == 'pending':
        #     domain.append(('transaction_state', '=', 'pendiente'))
        # elif mov_type == 'refused':
        #     domain.append(('transaction_state', '=', 'rechazado'))
        # elif mov_type == 'approved':
        #     domain.append(('transaction_state', '=', 'aprobado'))

        all_transactions = request.env['transfer.request'].sudo().search(domain)

        total_items = len(all_transactions)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        transactions = all_transactions[start_index:end_index]

        # Calcular las páginas visibles
        visible_pages = []
        if total_pages > 1:
            visible_pages = [1]  # Siempre mostrar la primera página
            if page > 4:
                visible_pages.append('...')

            for i in range(max(2, page - 2), min(total_pages, page + 3) + 1):
                visible_pages.append(i)

            if page < total_pages - 3:
                visible_pages.append('...')

            if total_pages not in visible_pages:
                visible_pages.append(total_pages)

        return request.render(
            'billetera_pagoflex.web_template_transfer_request',
            {
                'transactions': transactions,
                'current_page': page,
                'total_pages': total_pages,
                'visible_pages': visible_pages,
                'mov_type': mov_type,
            },
        )

    @route('/wallet/transfer_request/sended', auth='user', website=True)
    def send_transfer_request_sended(self, **kwargs):
        try:
            amount = kwargs.get('monto','0').replace('.','').replace(',','.')
            clean_amount = abs(float(amount))
            dict_data = {
                'date': kwargs.get('fecha'),
                'customer': request.env.user.partner_id.id,
                'description': kwargs.get('comentario'),
                'amount': clean_amount,
                'name_destination_account': kwargs.get('cuenta_destino'),
                'alias_destination_account': kwargs.get('alias'),
                'cvu_destination_account': kwargs.get('cvu'),
                'cuit_destination_account': kwargs.get('cuit'),
            }
            request.env['transfer.request'].sudo().create(dict_data)
            state_request = True
        except Exception as e:
            _logger.error(f'Error al crear la solicitud de transferencia: {e}')
            state_request = False

        return request.render('billetera_pagoflex.web_form_template_transfer_request_sended', {'state_request': state_request})

    @route('/wallet/transfer_request/cancel/<int:id>', auth='user', website=True)
    def cancel_transfer_request(self, **kwargs):
        domain = [('id', '=', kwargs['id'])]
        trans_req = request.env['transfer.request'].sudo().search(domain)
        if trans_req:
            if trans_req.transfer_request_state != 'pasado':
                trans_req.transfer_request_state = 'cancelado'
            else:
                message = 'No se puede cancelar un pedido de transferencia aprobado.'

        return request.redirect('/wallet/transfer_request')

    @route('/wallet/export_excel/<int:id_service>', auth='user', website=True)
    def export_excel(self, id_service,**kwargs):
        partner_id = request.env.user.partner_id.id
        doc_ids = request.env['collection.transaction'].sudo()
        data = request.env['collection.transaction'].sudo().search([('customer', '=', partner_id), ('collection_trans_type', '!=', 'movimiento_interno'),('service', '=', id_service)])

        buffer = BytesIO()
        workbook = xlsxwriter.Workbook(buffer)
        sheet = workbook.add_worksheet('Recaudación de Pago')

        bold = workbook.add_format({'bold': True, 'align': 'left'})
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        percent_fmt = workbook.add_format({'num_format': '0.00%'})

        sheet.set_column('A:A', 16)
        sheet.set_column('B:B', 14)
        sheet.set_column('C:C', 14)
        sheet.set_column('D:D', 22)
        sheet.set_column('E:E', 22)
        sheet.set_column('F:F', 14)
        sheet.set_column('G:G', 16)
        sheet.set_column('H:H', 16)
        sheet.set_column('I:I', 14)
        sheet.set_column('J:J', 14)
        sheet.set_column('K:K', 18)
        sheet.set_column('L:L', 10)
        sheet.set_column('M:M', 8)

        row = 0
        col = 0
        sheet.write(row, col, 'Fecha:', bold)
        sheet.write(row, col + 1, 'Nro T:', bold)
        sheet.write(row, col + 2, 'Cliente:', bold)
        sheet.write(row, col + 3, 'Servicio:', bold)
        sheet.write(row, col + 4, 'Operación:', bold)
        sheet.write(row, col + 5, 'CUIT:', bold)
        sheet.write(row, col + 6, 'Descripción:', bold)
        sheet.write(row, col + 7, 'Imp. Operación:', bold)
        sheet.write(row, col + 8, 'Comi(%):', bold)
        sheet.write(row, col + 9, 'Imp. Comisión:', bold)

        row = 1
        for rec in data:
            sheet.write(row, col, rec.date.strftime('%d/%m/%Y'))
            sheet.write(row, col + 1, rec.transaction_name)
            sheet.write(row, col + 2, rec.customer.name)
            sheet.write(row, col + 3, rec.service.services.name)
            sheet.write(row, col + 4, rec.operation.name)
            sheet.write(row, col + 5, rec.origin_account_cuit)
            sheet.write(row, col + 6, rec.description)
            sheet.write(row, col + 7, rec.amount)
            sheet.write(row, col + 8, rec.commission)
            sheet.write(row, col + 9, (rec.commission * rec.amount) / 100)
            row += 1

        workbook.close()
        buffer.seek(0)

        headers = [('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), ('Content-Disposition', content_disposition(f'{request.env.user.partner_id.name}.xlsx'))]
        return request.make_response(buffer.getvalue(), headers=headers)
