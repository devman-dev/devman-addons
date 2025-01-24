import io
import xlsxwriter
from odoo import models, fields, api
from odoo.http import content_disposition, request

class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    def action_smart_button_exportar_xlsx(self):
        encuesta = self.env['survey.user_input.line'].search([('survey_id', '=', self.id)])

        users = []
        l = ""
        ll = "Ingresar su primer y segundo nombre;Ingresar su apellido;Ingresar DNI;Ingrese su localidad;Ingrese su dirección;Fecha de nacimiento;Cuál es tu número de celular;Ingresar tu correo electrónico;Cómo prefieres votar"
        n = 0
        nn = []
        error = 0

        for r in encuesta:
            if r.user_input_id.id not in users:
                users.append(r.user_input_id.id)

        for user in users:
            for r in encuesta:
                if r.user_input_id.id == user:
                    if l != "":
                        l = l + ";"
                    l = l + r.display_name
            ll = ll + "\n" + l
            l = ""

        # Crear el archivo Excel en memoria
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Escribir los datos en el archivo Excel
        row = 0
        for line in ll.split('\n'):
            col = 0
            for cell in line.split(';'):
                worksheet.write(row, col, cell)
                col += 1
            row += 1

        workbook.close()
        output.seek(0)

        # Devolver el archivo Excel como una descarga
        return request.make_response(
            output.read(),
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', content_disposition('survey_responses.xlsx'))
            ]
        )