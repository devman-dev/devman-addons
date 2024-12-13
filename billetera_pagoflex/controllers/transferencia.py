from odoo.http import request, Controller, route


class WebFormWalletController(Controller):
    @route('/wallet', auth='user', website=True)
    def web_form_wallet(self, **kwargs):
        customer = request.env['collection.dashboard.customer'].search([('customer', '=', request.env.user.partner_id.id)])
        available_balance = customer.customer_available_balance if customer else 0.00
        return request.render('billetera_pagoflex.web_form_template_wallet', {'available_balance': available_balance})


    @route('/wallet/transfer/accounts', auth='public', website=True, methods=['GET'])
    def web_form_transfer(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer')

    @route('/wallet/transfer/accounts/new_account', auth='public', website=True, methods=['GET'])
    def web_form_transfer_new_account(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_new_account')
    
    @route('/wallet/transfer/accounts/new_account/search', auth='public', website=True, methods=['GET'])
    def web_form_transfer_new_account_search(self, **kwargs):
        return request.render('billetera_pagoflex.web_form_template_transfer_new_account_search')