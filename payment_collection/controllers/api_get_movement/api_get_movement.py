# -*- coding: utf-8 -*-
from odoo import http


from odoo.http import request

from . api_get_movement_transaction import GetCustomerMovement


class WebControllerGetMovement(http.Controller):
    @http.route('/api/url/get_movement', auth='user', type='json', website=True)
    def url_get_movement(self, **datos):
        try:
            a = GetCustomerMovement.get_customer_movement_transaccion(self, datos)
            return a
        except Exception as invalid_user:
            return  invalid_user