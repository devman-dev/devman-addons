from odoo import fields, models, api, _


class ReportPrestamoBancarioXlsx(models.AbstractModel):
    _name = 'report.payment_collection.report_collection_transaction_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, partners):
        data = data
        nombre_sheet = data['nombre']
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
        sheet.write(row, col + 1, data['fecha'])
        sheet.write(row + 1, col, 'Nombre:', bold)
        sheet.write(row + 1, col + 1, data['nombre'])
        sheet.write(row + 2, col, 'Cliente:', bold)
        sheet.write(row + 2, col + 1, data['cliente'])
        sheet.write(row, col + 4, 'Tipo de Metodo:', bold)
        sheet.write(row, col + 5, data['tipo_metodo'])
        sheet.write(row + 1, col + 4, 'Tipo de Tasa de Interes:', bold)
        sheet.write(row + 1, col + 5, data['tipo_tasa_interes'])