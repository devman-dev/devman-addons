from odoo.http import request, Controller, route
import requests
import json


class WebFormWalletController(Controller):
    @route('/wallet', auth='user', website=True)
    def web_form_wallet(self, **kwargs):
        customer = request.env['collection.dashboard.customer'].sudo().search([('customer', '=', request.env.user.partner_id.id)])
        customer_balance = customer.collection_balance if customer else 0.00
        transactions = (
            request.env['collection.transaction'].sudo().search([('customer', '=', request.env.user.partner_id.id), ('collection_trans_type', '!=', 'movimiento_interno')], order='id desc', limit=10)
        )
        return request.render('billetera_pagoflex.web_template_wallet', {'customer_balance': customer_balance, 'transactions': transactions})

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
        return request.render('billetera_pagoflex.transfer_account_template', {'account': account})

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
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page

        transactions = all_transactions[start_index:end_index]

        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        customer = request.env['collection.dashboard.customer'].sudo().search([('customer', '=', request.env.user.partner_id.id)])
        customer_balance = customer.collection_balance if customer else 0.00

        return request.render(
            'billetera_pagoflex.web_template_movements',
            {
                'transactions': transactions,
                'current_page': page,
                'total_pages': total_pages,
                'mov_type': mov_type,
                'customer_balance': customer_balance,
            },
        )
