# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import base64
import csv
from io import StringIO

class ProjectDataImportWizard(models.TransientModel):
    _name = "project.data.import.wizard"
    _description = "Importación CSV de datos de referencia"

    data_type = fields.Selection([("role_rate","Tarifas por rol"),("employee_cost","Costos por empleado"),("complexity","Factores de complejidad")], required=True)
    file = fields.Binary(string="Archivo CSV", required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        content = base64.b64decode(self.file or b"")
        csvfile = StringIO(content.decode("utf-8"))
        reader = csv.DictReader(csvfile)
        if self.data_type == "role_rate":
            for row in reader:
                role = self.env["project.role"].search([("code","=",row.get("role_code"))], limit=1)
                if not role:
                    role = self.env["project.role"].create({"name": row.get("role_name"), "code": row.get("role_code")})
                self.env["project.role.rate"].create({
                    "role_id": role.id,
                    "rate_hour": float(row.get("rate_hour", 0)),
                    "currency_id": self.env.company.currency_id.id,
                })
        elif self.data_type == "employee_cost":
            for row in reader:
                emp = self.env["hr.employee"].search([("work_email","=",row.get("email"))], limit=1)
                if not emp:
                    emp = self.env["hr.employee"].create({"name": row.get("name"), "work_email": row.get("email")})
                self.env["employee.hourly.cost"].create({
                    "employee_id": emp.id,
                    "cost_hour": float(row.get("cost_hour", 0)),
                    "date_from": row.get("date_from"),
                    "date_to": row.get("date_to") or False,
                    "currency_id": self.env.company.currency_id.id,
                })
        else:
            for row in reader:
                self.env["project.complexity.ref"].create({"name": row.get("name"), "factor": float(row.get("factor", 1.0))})
        return {"type": "ir.actions.act_window_close"}