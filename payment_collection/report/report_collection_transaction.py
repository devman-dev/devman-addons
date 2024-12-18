from odoo import models

class ReportPrestamoBancarioXlsx(models.AbstractModel):
    _name = 'report.payment_collection.report_collection_transaction_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, partners):
        data = data
        nombre_sheet = 'Recaudación de Pagos'
        sheet = workbook.add_worksheet(nombre_sheet)
        bold = workbook.add_format({'bold': True, 'align': 'left'})
        bold_center = workbook.add_format({'bold': True, 'align': 'center'})
        number_format = workbook.add_format({'num_format': '#,##0.00'})
        percent_fmt = workbook.add_format({'num_format': '0.00%'})

        sheet.set_column('A:A', 16)
        sheet.set_column('B:B', 14)
        sheet.set_column('C:C', 14)
        sheet.set_column('D:D', 22)
        sheet.set_column('E:E', 22)
        sheet.set_column('F:F', 14)
        sheet.set_column('G:G', 16)
        sheet.set_column('H:H', 16)
        sheet.set_column('I:I', 14)
        sheet.set_column('J:J', 14)
        sheet.set_column('K:K', 18)
        sheet.set_column('L:L', 10)
        sheet.set_column('M:M', 8)

        row = 0
        col = 0
        sheet.write(row, col, 'Fecha:', bold)
        sheet.write(row, col + 1, 'Nro T:', bold)
        sheet.write(row, col + 2, 'Cliente:', bold)
        sheet.write(row, col + 3, 'Servicio:', bold)
        sheet.write(row, col + 4, 'Operación:', bold)
        sheet.write(row, col + 5, 'CUIT:', bold)
        sheet.write(row, col + 6, 'Descripción:', bold)
        sheet.write(row, col + 7, 'Imp. Operación:', bold)
        sheet.write(row, col + 8, 'Comi(%):', bold)
        sheet.write(row, col + 9, 'Imp. Comisión:', bold)

        row = 1
        for rec in partners:
            sheet.write(row, col, rec.date.strftime('%d/%m/%Y'))
            sheet.write(row, col + 1, rec.transaction_name )
            sheet.write(row, col + 2, rec.customer.name )
            sheet.write(row, col + 3, rec.service.services.name )
            sheet.write(row, col + 4, rec.operation.name )
            sheet.write(row, col + 5, rec.origin_account_cuit )
            sheet.write(row, col + 6, rec.description )
            sheet.write(row, col + 7, rec.amount )
            sheet.write(row, col + 8, rec.commission )
            sheet.write(row, col + 9, (rec.commission * rec.amount) / 100 )
            row += 1
