from odoo import fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class CommiTransWiz(models.TransientModel):
    _name = 'commi.trans.wiz'

    previous_balance = fields.Float('Saldo anterior',)
    start_date = fields.Date('Fecha de inicio', required=True, default=lambda self: fields.Date.today() - relativedelta(months=1))
    end_date = fields.Date('Fecha Fin', required=True, default=fields.Date.today)
    customer = fields.Many2one('res.partner', string='Cliente', required=True)
    total_balance = fields.Float('Saldo Total')


    def print(self):
        start_date = self.start_date
        end_date = self.end_date
        customer = self.customer

        domain = [('date', '<', start_date), ('customer', '=', customer.id)]
        previous_months = self.env['collection.transaction'].search(domain)

        self.previous_balance = sum([pm.amount for pm in previous_months])
        dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', self.customer.id)])
        dashboard_customer.update_available_balance()
        domain_2 = [('date', '>=', start_date), ('date', '<=', end_date),('customer', '=', customer.id)]
        filtered_records = self.env['collection.transaction'].search(domain_2)
        if filtered_records:
            filtered_records[0].available_balance = dashboard_customer.customer_available_balance
            filtered_records[0].previous_month = self.previous_balance

            return self.env.ref('payment_collection.action_report_collection_transaction').report_action(filtered_records)
        else:
            raise ValidationError('No se encontraron registros para ese cliente entre las fechas definidas para agregar al reporte.')