# -*- coding: utf-8 -*-
from odoo import http


from odoo.http import request

from . get_balance_transaction import GetCustomerBalance


class WebControllerGetBalance(http.Controller):
    @http.route('/api/url/get_balance', auth='user', type='json', website=True)
    def url_get_balance(self, **datos):
        try:
            a = GetCustomerBalance.get_customer_balance_transaccion(self, datos)
            return a
        except Exception as invalid_user:
            return  invalid_user

