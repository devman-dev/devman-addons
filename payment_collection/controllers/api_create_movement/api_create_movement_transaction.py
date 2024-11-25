import json
import odoo.http as http

from odoo.http import request
from datetime import *

import requests

class CreateMovement():
    def create_movement(self, datos):
        try:
            movement = {
                'customer': datos['partner_id'],
                'date': datos['date'],
                'service': datos['service'],
                'amount': datos['amount'],
                'operation': datos['operation'],
                'cuit_destination_account': datos['cuit'],
                'cbu_destination_account': datos['cbu'],
                'cvu_destination_account': datos['cvu'],
                'alias_destination_account': datos['alias'],
                'count': 0,
                'collection_trans_type':'movimiento_recaudacion',
                # 'name_destination_account': datos[''] # REVISAR CAMPO
            }
            create_movement = request.env['collection.transaction'].sudo().create(movement)
            return 200
        except Exception as error_create:
            return 400

