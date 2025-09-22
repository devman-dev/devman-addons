# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ProjectRole(models.Model):
    _name = "project.role"
    _description = "Rol de Proyecto"
    _rec_name = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    description = fields.Text()

class HrTeam(models.Model):
    _name = "hr.team"
    _description = "Equipo de RRHH (custom)"
    name = fields.Char(required=True)
    manager_id = fields.Many2one("hr.employee", string="Responsable")
    member_ids = fields.Many2many("hr.employee", string="Miembros")

class ProjectComplexityRef(models.Model):
    _name = "project.complexity.ref"
    _description = "Referencia de Complejidad"
    name = fields.Char(required=True)
    factor = fields.Float(string="Factor de complejidad", default=1.0)

class ProjectRoleRate(models.Model):
    _name = "project.role.rate"
    _description = "Tarifa por Rol"
    role_id = fields.Many2one("project.role", required=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id, required=True)
    rate_hour = fields.Monetary(string="Tarifa por hora", required=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company, required=True)

class EmployeeHourlyCost(models.Model):
    _name = "employee.hourly.cost"
    _description = "Costo por Hora de Empleado"
    employee_id = fields.Many2one("hr.employee", required=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id, required=True)
    cost_hour = fields.Monetary(required=True)
    date_from = fields.Date(required=True)
    date_to = fields.Date()
    active = fields.Boolean(default=True)