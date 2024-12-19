from odoo.http import request, Controller, route
import requests
import json


class WebFormWalletController(Controller):
    @route('/wallet', auth='user', website=True)
    def web_form_wallet(self, **kwargs):
        customer = request.env['collection.dashboard.customer'].search([('customer', '=', request.env.user.partner_id.id)])
        available_balance = customer.customer_available_balance if customer else 0.00
        return request.render('billetera_pagoflex.web_form_template_wallet', {'available_balance': available_balance})

    @route('/wallet/transfer/accounts', auth='user', website=True, methods=['GET'])
    def web_form_transfer(self, **kwargs):
        data = requests.get('http://localhost:8017/bank/get_data')
        response = data.json()
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
            'cuit': '12345678901'
        }
        return request.render('billetera_pagoflex.web_form_template_transfer_confirm_account',{'account':account})



    @route('/wallet/transfer/accounts/new_account/search', auth='user', website=True, methods=['GET'])
    def web_form_transfer_new_account_search(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_new_account_search')

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

        account = {
            'id': '2',
            'cbu': '1234567890112345678901',
            'cvu': '1234567890112345678901',
            'alias': 'alias.demo2',
            'name_account': 'Datos Demostracion2',
            'cuit': '12345678901'
        }
        return request.render('billetera_pagoflex.web_form_template_transfer_account_revision', {'account': account,'amount': 100})


    @route('/wallet/transfer/sended', auth='user', website=True)
    def transfer_sended(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_sended')


