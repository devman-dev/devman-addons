from odoo import fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class CommiTransWiz(models.TransientModel):
    _name = 'commi.trans.wiz'

    previous_balance = fields.Float('Saldo anterior',)
    start_date = fields.Date('Fecha de inicio', required=True, default=lambda self: fields.Date.today() - relativedelta(months=1))
    end_date = fields.Date('Fecha Fin', required=True, default=fields.Date.today)
    customer = fields.Many2one('res.partner', string='Cliente', required=True, domain="[('check_origin_account','!=', True)]")
    total_balance = fields.Float('Saldo Total')


    def print(self):
        start_date = self.start_date
        end_date = self.end_date
        customer = self.customer

        previous_month_pesos = 0
        previous_month_usd = 0
        previous_month_euros = 0
        previous_month_reales = 0


        domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno')]
        previous_months = self.env['collection.transaction'].search(domain)
        if previous_months:
            for rec in previous_months:
                if rec.currency_id.name == "ARS":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_pesos = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "USD":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_usd = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "EUR":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_euros = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "BRL":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_reales = sum([pm.amount for pm in previous_months])


        self.previous_balance = sum([pm.amount for pm in previous_months])
        dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', self.customer.id)], limit=1)
        dashboard_customer.update_available_balance()
        domain_2 = [('date', '>=', start_date), ('date', '<=', end_date),('customer', '=', customer.id),('collection_trans_type', '!=', 'movimiento_interno')]
        filtered_records = self.env['collection.transaction'].search(domain_2, order='date asc, id desc')
        if filtered_records:
            filtered_records[0].sudo().write({
                'previous_month': self.previous_balance,
                'previous_month_pesos': previous_month_pesos,
                'previous_month_usd': previous_month_usd,
                'previous_month_euros': previous_month_euros,
                'previous_month_reales': previous_month_reales,
                'available_balance': dashboard_customer.customer_available_balance,
                'start_date': start_date, 
                'end_date': end_date,
                'print_date': datetime.now(),
            })
            

            return self.env.ref('payment_collection.action_report_collection_transaction').report_action(filtered_records)
        else:
            raise ValidationError('No se encontraron registros para ese cliente entre las fechas definidas para agregar al reporte.')

    def print_xlsx(self):
        start_date = self.start_date
        end_date = self.end_date
        customer = self.customer

        previous_month_pesos = 0
        previous_month_usd = 0
        previous_month_euros = 0
        previous_month_reales = 0

        domain = [('date', '<', start_date), ('customer', '=', customer.id),
                  ('collection_trans_type', '!=', 'movimiento_interno')]
        previous_months = self.env['collection.transaction'].search(domain)

        if previous_months:
            for rec in previous_months:
                if rec.currency_id.name == "ARS":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),
                              ('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_pesos = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "USD":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),
                              ('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_usd = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "EUR":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),
                              ('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_euros = sum([pm.amount for pm in previous_months])

                if rec.currency_id.name == "BRL":
                    domain = [('date', '<', start_date), ('customer', '=', customer.id),
                              ('collection_trans_type', '!=', 'movimiento_interno'),
                              ('currency_id', '=', rec.currency_id.id)]
                    previous_months = self.env['collection.transaction'].search(domain)
                    previous_month_reales = sum([pm.amount for pm in previous_months])


        self.previous_balance = sum([pm.amount for pm in previous_months])
        dashboard_customer = self.env['collection.dashboard.customer'].search([('customer', '=', self.customer.id)],
                                                                              limit=1)
        dashboard_customer.update_available_balance()
        domain_2 = [('date', '>=', start_date), ('date', '<=', end_date), ('customer', '=', customer.id),
                    ('collection_trans_type', '!=', 'movimiento_interno')]
        filtered_records = self.env['collection.transaction'].search(domain_2, order='date asc, id desc')
        if filtered_records:
            filtered_records[0].sudo().write({
                'previous_month': self.previous_balance,
                'previous_month_pesos': previous_month_pesos,
                'previous_month_usd': previous_month_usd,
                'previous_month_euros': previous_month_euros,
                'previous_month_reales': previous_month_reales,
                'available_balance': dashboard_customer.customer_available_balance,
                'start_date': start_date,
                'end_date': end_date,
                'print_date': datetime.now(),
            })

            return self.env.ref('payment_collection.report_collection_transaction_xlsx_id').report_action(
                filtered_records)
        else:
            raise ValidationError(
                'No se encontraron registros para ese cliente entre las fechas definidas para agregar al reporte.')