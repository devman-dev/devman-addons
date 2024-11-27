import json
import odoo.http as http

from odoo.http import request
from datetime import *

import requests

class GetCustomerMovement():
    def get_customer_movement_transaccion(self, datos):
        client_name = datos['partner_id']

        client = request.env['res.partner'].sudo().search([('name', '=', client_name)])
        client_id = client.id

        get_movement = request.env['collection.transaction'].sudo().search([('customer', '=', client_id),('collection_trans_type','!=','movimiento_interno')])
        movement_list = []
        for movement in get_movement:
            movement_dict = {'date': movement.date,
                             'service': movement.service.services.name,
                             'operation': movement.operation.display_name,
                             'amount': movement.amount,
                             }
            movement_list.append(movement_dict)

        customer_balance = {'client_name': client_name,
                            'movimientos':movement_list
                            }
        return customer_balance