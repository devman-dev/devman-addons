import json
import odoo.http as http

from odoo.http import request
from datetime import *

import requests

class GetCustomerServices():
    def get_customer_services_transaccion(self, datos):
        id = datos['partner_id']

        client = request.env['res.partner'].sudo().search([('id', '=', id)])
        client_id = client.id

        get_services = request.env['collection.services.commission'].sudo().search([('customer', '=', client_id)])
        services_list = []
        for service in get_services:
            service_dict = {'id': service.id,
                            'service': service.services.name
                            }
            services_list.append(service_dict)

        services = {'client_id': client_id,
                    'services': services_list
                    }

        return services