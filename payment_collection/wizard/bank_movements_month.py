from odoo import fields, models
from datetime import datetime
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

class BankMovementsMonth(models.TransientModel):
    _name = 'bank.movements.month.wiz'


    start_date = fields.Date('Fecha de inicio', required=True, default=lambda self: fields.Date.today() - relativedelta(months=1))
    end_date = fields.Date('Fecha Fin', required=True, default=fields.Date.today)
    list_name_account = fields.Many2one('list.name.account', string="Banco")

    def print(self):
        start_date = self.start_date
        end_date = self.end_date
        list_name_account = self.list_name_account


        domain_2 = [('date', '>=', start_date), ('date', '<=', end_date),'|',('origin_account.name_account', '=', list_name_account.name),('destination_account.name_account', '=', list_name_account.name)]
        filtered_records = self.env['collection.transaction'].search(domain_2, order='date asc, id asc')
        if filtered_records:
            return self.env.ref('payment_collection.report_bank_movement_month_xlsx_id').report_action(filtered_records)
        else:
            raise ValidationError('No se encontraron registros para ese cliente entre las fechas definidas para agregar al reporte.')