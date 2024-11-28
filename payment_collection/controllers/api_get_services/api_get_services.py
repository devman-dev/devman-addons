# -*- coding: utf-8 -*-
from odoo import http


from odoo.http import request

from . api_get_services_transaction  import GetCustomerServices


class WebControllerGetBalance(http.Controller):
    @http.route('/api/url/get_services', auth='user', type='json', website=True)
    def url_get_balance(self, **datos):
        try:
            a = GetCustomerServices.get_customer_services_transaccion(self, datos)
            return a
        except Exception as invalid_user:
            return  invalid_user