from odoo import fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class CommiTransWiz(models.TransientModel):
    _name = 'recalculate.button.wiz'

    all_customer_dash = fields.Many2many('recalculate.table')


    def imputar(self):
        for reg in self.all_customer_dash:
            try:
                dashboard = self.env['collection.dashboard.customer'].sudo().search([('customer', '=', reg.customer.id)],)
                if dashboard:
                    dashboard.sudo().write(
                        {'customer': reg.customer.id,
                         'customer_real_balance': reg.customer_real_balance,
                         'customer_available_balance': reg.customer_available_balance,
                         'collection_balance': reg.collection_balance,
                         'commission_balance': reg.commission_balance,
                         'commission_app_rate': reg.commission_app_rate,
                         'commission_app_amount': reg.commission_app_amount,
                         'last_operation_date': reg.last_operation_date,
                         })
                else:
                    last_operation = self.env['collection.transaction'].search([('customer','=',reg.customer.id)],limit=1)
                    last_operation_date = last_operation[-1].write_date
                    dashboard.sudo().create(
                        {'customer': reg.customer.id,
                         'customer_real_balance': reg.customer_real_balance,
                         'customer_available_balance': reg.customer_available_balance,
                         'collection_balance': reg.collection_balance,
                         'commission_balance': reg.commission_balance,
                         'commission_app_rate': reg.commission_app_rate,
                         'commission_app_amount': reg.commission_app_amount,
                         'last_operation_date': last_operation_date,
                         })
            except Exception as error_create:
                print('error creando dashboard:', error_create)




class RecalculateTransWiz(models.TransientModel):
    _name = 'recalculate.table'

    customer = fields.Many2one('res.partner', string='Cliente', domain="[('check_origin_account','!=', True)]")
    customer_real_balance = fields.Float(string='Saldo Real App')
    customer_available_balance = fields.Float(string='Saldo Disponible')
    collection_balance = fields.Float(string='Saldo Total Cliente')
    last_operation_date = fields.Date(string='Fecha de ultima operación')
    commission_balance = fields.Float(string='Saldo de Comisión')
    commission_app_rate = fields.Float(string='Comi. App (%)')
    commission_app_amount = fields.Float(string='Monto App')