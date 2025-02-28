from odoo.http import request, Controller, route
import requests
import json


class WebFormWalletController(Controller):
    @route('/wallet', auth='user', website=True)
    def web_form_wallet(self, **kwargs):
        collection_balance = request.env['collection.dashboard.customer'].sudo().recalculate_total_recs(request.env.user.partner_id.id)
        customer_balance = collection_balance if collection_balance else 0.00
        transactions = (
            request.env['collection.transaction'].sudo().search([('customer', '=', request.env.user.partner_id.id), ('collection_trans_type', '!=', 'movimiento_interno')], order='id desc', limit=10)
        )
        return request.render('billetera_pagoflex.web_template_wallet', {'customer_balance': customer_balance, 'transactions': transactions, 'user_name': request.env.user.name})

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
        account = {'id': '2', 'cbu': '1234567890112345678901', 'cvu': '1234567890112345678901', 'alias': 'alias.demo2', 'name_account': 'Datos Demostracion2', 'cuit': '12345678901'}
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
        account = {'id': '2', 'cbu': '1234567890112345678901', 'cvu': '1234567890112345678901', 'alias': 'alias.demo2', 'name_account': 'Datos Demostracion2', 'cuit': '12345678901'}
        return request.render('billetera_pagoflex.web_form_template_transfer_account_revision', {'account': account, 'amount': 100})

    @route('/wallet/transfer/sended', auth='user', website=True)
    def transfer_sended(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_sended')

    @route('/wallet/movements/<string:mov_type>/<int:page>', auth='user', website=True)
    def show_movements(self, mov_type, page=1, **kwargs):
        items_per_page = 10

        domain = [('customer', '=', request.env.user.partner_id.id)]
        if mov_type == 'pending':
            domain.append(('transaction_state', '=', 'pendiente'))
        elif mov_type == 'refused':
            domain.append(('transaction_state', '=', 'rechazado'))
        elif mov_type == 'approved':
            domain.append(('transaction_state', '=', 'aprobado'))

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
            },
        )

    @route('/wallet/transfer_request', auth='user', website=True)
    def send_transfer_request(self,**kwargs):
        return request.render('billetera_pagoflex.web_form_template_request_transfer')


    @route('/wallet/tranfers_request/<string:mov_type>/<int:page>', auth='user', website=True)
    def show_movements(self, mov_type, page=1, **kwargs):
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
            dict_data = {
                'date': kwargs.get('fecha'),
                'customer': request.env.user.partner_id.id,
                'description': kwargs.get('comentario'),
                'amount': abs(float(kwargs.get('monto'))) * -1,
                'name_destination_account': kwargs.get('cuenta_destino'),
                'alias_destination_account': kwargs.get('alias'),
                'cbu_destination_account': kwargs.get('cbu'),
                'cvu_destination_account': kwargs.get('cvu'),
            }
            request.env['transfer.request'].sudo().create(dict_data)
            state_request = True
        except:
            state_request = False

        return request.render('billetera_pagoflex.web_form_template_transfer_request_sended', {'state_request': state_request})


    @route('/wallet/transfer_request/cancel/<int:id>', auth='user', website=True)
    def cancel_transfer_request(self, **kwargs):
        domain = [('id','=', kwargs['id'])]
        trans_req = request.env['transfer.request'].sudo().search(domain)
        if trans_req:
            if trans_req.transfer_request_state != 'pasado':
                trans_req.transfer_request_state = 'cancelado'
            else:
                message = 'No se puede cancelar un pedido de transferencia aprobado.'


        return request.render('billetera_pagoflex.web_form_template_request_transfer')

