from odoo import fields, models
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError

class ReportAgentWiz(models.TransientModel):
    _name = 'report.agent.wiz'

    previous_balance = fields.Float('Saldo anterior',)
    start_date = fields.Date('Fecha de inicio', required=True, default=lambda self: fields.Date.today() - relativedelta(months=1))
    end_date = fields.Date('Fecha Fin', required=True, default=fields.Date.today)
    agent = fields.Many2one('res.partner', string='Agente', required=True)
    total_balance = fields.Float('Saldo Total')


    def print(self):
        start_date = self.start_date
        end_date = self.end_date
        agent = self.agent

        domain = [('date', '<', start_date), ('agent', '=', agent.id)]
        previous_months = self.env['collection.transaction.commission'].search(domain)

        self.previous_balance = sum([pm.commission_amount for pm in previous_months])

        domain_2 = [('date', '>=', start_date), ('date', '<=', end_date),('agent', '=', agent.id)]
        filtered_records = self.env['collection.transaction.commission'].search(domain_2)
        if filtered_records:
            filtered_records[0].previous_month = self.previous_balance

            return self.env.ref('payment_collection.action_report_collection_transaction_commission').report_action(filtered_records)

        else:
            raise ValidationError(
                'No se encontraron registros para ese agente entre las fechas definidas para agregar al reporte.')


