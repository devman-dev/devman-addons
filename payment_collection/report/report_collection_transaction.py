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
        # number_format = workbook.add_format({'num_format': '#.##0,00'})
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

        sheet.write(0,0, 'Cliente: ', bold)
        sheet.write(0, 1, partners[0].customer.name)

        sheet.write(1, 0, 'Fecha desde: ', bold)
        sheet.write(1, 1, partners[0].start_date.strftime('%d/%m/%Y'))

        sheet.write(1, 2, 'Fecha hasta: ', bold)
        sheet.write(1, 3, partners[0].end_date.strftime('%d/%m/%Y'))

        sheet.write(1, 5, 'Saldo Anterior: ', bold)
        sheet.write(1, 6, partners[0].previous_month)


        row = 2
        col = 0
        sheet.write(row, col, 'Fecha:', bold)
        sheet.write(row, col + 1, 'Nro T:', bold)
        sheet.write(row, col + 2, 'Servicio:', bold)
        sheet.write(row, col + 3, 'Operación:', bold)
        sheet.write(row, col + 4, 'CUIT:', bold)
        sheet.write(row, col + 5, 'Descripción:', bold)
        sheet.write(row, col + 6, 'Imp. Operación:', bold)
        sheet.write(row, col + 7, 'Comi(%):', bold)
        sheet.write(row, col + 8, 'Imp. Comisión:', bold)

        row = 3
        total_amount = 0
        for rec in partners:
            sheet.write(row, col, rec.date.strftime('%d/%m/%Y'))
            if rec.transaction_name:
                sheet.write(row, col + 1, rec.transaction_name)
            else:
                sheet.write(row, col + 1, '')

            if rec.service.services.name:
                sheet.write(row, col + 2, rec.service.services.name)
            else:
                sheet.write(row, col + 2, '')

            if rec.operation.name:
                sheet.write(row, col + 3, rec.operation.name)
            else:
                sheet.write(row, col + 3, '')

            if rec.origin_account_cuit:
                sheet.write(row, col + 4, rec.origin_account_cuit)
            else:
                sheet.write(row, col + 4, '')

            if rec.description:
                sheet.write(row, col + 5, rec.description)
            else:
                sheet.write(row, col + 5, '')

            if rec.amount:
                sheet.write(row, col + 6, rec.amount, number_format)
            else:
                sheet.write(row, col + 6, '', number_format)

            if rec.commission:
                sheet.write(row, col + 7, rec.commission, percent_fmt)
            else:
                sheet.write(row, col + 7, '', percent_fmt)

            sheet.write(row, col + 8, (rec.commission * rec.amount) / 100, number_format)

            row += 1
            total_amount += rec.amount

        sheet.write(row, 5, 'Saldo Final: ', bold)
        sheet.write(row, 6, total_amount, number_format)