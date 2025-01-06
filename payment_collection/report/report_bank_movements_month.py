from odoo import models

class ReportBankMovementMonthXlsx(models.AbstractModel):
    _name = 'report.payment_collection.report_bank_movement_month_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, partners):
        data = data
        nombre_sheet = 'Movimientos bancarios'
        sheet = workbook.add_worksheet(nombre_sheet)
        bold = workbook.add_format({'bold': True, 'align': 'left'})
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        percent_fmt = workbook.add_format({'num_format': '0.00%'})

        sheet.set_column('A:A', 16)
        sheet.set_column('B:B', 18)
        sheet.set_column('C:C', 18)
        sheet.set_column('D:D', 13)
        sheet.set_column('E:E', 22)
        sheet.set_column('F:F', 18)
        sheet.set_column('G:G', 18)
        sheet.set_column('H:H', 18)
        sheet.set_column('I:I', 18)

        row = 0
        col = 0
        sheet.write(row, col, 'Fecha:', bold)
        sheet.write(row, col + 1, 'Cuenta Origen:', bold)
        sheet.write(row, col + 2, 'Cuenta Destino:', bold)
        sheet.write(row, col + 3, 'Nro T:', bold)
        sheet.write(row, col + 4, 'Cliente:', bold)
        sheet.write(row, col + 5, 'Servicio:', bold)
        sheet.write(row, col + 6, 'Operación:', bold)
        sheet.write(row, col + 7, 'Descripción:', bold)
        sheet.write(row, col + 8, 'Imp. Operación:', bold)

        row = 1
        for rec in partners:
            sheet.write(row, col, rec.date.strftime('%d/%m/%Y'))
            sheet.write(row, col + 1, rec.origin_account.name_account)
            sheet.write(row, col + 2, rec.destination_account.name_account)
            sheet.write(row, col + 3, rec.transaction_name )
            sheet.write(row, col + 4, rec.customer.name )
            sheet.write(row, col + 5, rec.service.services.name )
            sheet.write(row, col + 6, rec.operation.name )
            sheet.write(row, col + 7, rec.description )
            sheet.write(row, col + 8, rec.amount )
            row += 1