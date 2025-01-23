import json
import odoo.http as http

from odoo.http import request
from datetime import *

import requests

class GetCustomerBalance():
    def get_customer_balance_transaccion(self, datos):
        client_id = datos['partner_id']

        client_balance = request.env['collection.dashboard.customer'].sudo().search([('customer', '=', client_id)])

        # client_available_balance =  client_balance.customer_available_balance
        client_total_balance = client_balance.collection_balance

        customer_balance = {
                            # 'available_balance': client_available_balance,
                            'total_balance': client_total_balance,
                            }
        return customer_balance