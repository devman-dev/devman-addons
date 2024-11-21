# -*- coding: utf-8 -*-
from odoo import http


from odoo.http import request

from . api_create_movement_transaction  import CreateMovement


class WebControllerGetBalance(http.Controller):
    @http.route('/api/url/create_movement', auth='user', type='json', website=True)
    def url_get_balance(self, **datos):
        try:
            a = CreateMovement.create_movement(self, datos)
            return a
        except Exception as invalid_user:
            return  invalid_user