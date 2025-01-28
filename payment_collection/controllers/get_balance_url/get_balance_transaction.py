import json
import odoo.http as http

from odoo.http import request
from datetime import *

import requests

class GetCustomerBalance():
    def get_customer_balance_transaccion(self, datos):
        client_id = datos['partner_id']

        client_total_balance = request.env['collection.dashboard.customer'].recalculate_total_recs(partner_id=client_id)

        customer_balance = {
                            'total_balance': client_total_balance,
                            }
        return customer_balance