# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ProjectFinancing(models.Model):
    _name = "project.financing"
    _description = "Financiamiento de Proyecto"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    quotation_id = fields.Many2one("project.quotation", required=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    lead_id = fields.Many2one("crm.lead", string="Oportunidad", required=True)
    team_id = fields.Many2one("hr.team", string="Equipo")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id.id, required=True)

    financing_type = fields.Selection([("cash","Contado"),("installments","Cuotas"),("mixed","Mixto")], string="Tipo de financiación", default="cash")

    usd_rate = fields.Float(string="Tipo de cambio USD", default=1.0)
    cost_line_ids = fields.One2many("project.financing.cost.line", "financing_id", string="Gastos/Servicios USD")

    role_breakdown_ids = fields.One2many("project.financing.role.breakdown", "financing_id", string="Distribución por Rol")

    employee_allocation_ids = fields.One2many("project.financing.employee.allocation", "financing_id", string="Asignación de Empleado")

    revenue = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    discount_percent = fields.Float(string="Descuento %")
    revenue_after_discount = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    expenses_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    team_cost_total = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    profit = fields.Monetary(compute="_compute_totals", store=True, currency_field="currency_id")
    margin_net = fields.Float(compute="_compute_totals", store=True, string="Margen Neto %")

    note = fields.Text()

    def action_view_summary(self):
        summary = self.env["project.quotation.summary"].create({
            "quotation_id": self.quotation_id.id,
            "financing_id": self.id,
            "lead_id": self.lead_id.id,
            "partner_id": self.partner_id.id,
            "observations": self.note or "",
        })
        action = self.env.ref("project_quotation_financing.action_project_quotation_summary").read()[0]
        action["res_id"] = summary.id
        action["view_mode"] = "form"
        return action

    @api.depends(
        "role_breakdown_ids.subtotal",
        "discount_percent",
        "cost_line_ids.subtotal_converted",
        "employee_allocation_ids.subtotal_cost"
    )
    def _compute_totals(self):
        for rec in self:
            revenue = sum(rec.role_breakdown_ids.mapped("subtotal"))
            revenue_after_discount = revenue * (1 - (rec.discount_percent or 0.0) / 100.0)
            expenses = sum(rec.cost_line_ids.mapped("subtotal_converted"))
            team_cost = sum(rec.employee_allocation_ids.mapped("subtotal_cost"))
            profit = revenue_after_discount - expenses - team_cost
            margin_net = (profit / revenue_after_discount * 100.0) if revenue_after_discount else 0.0
            rec.revenue = revenue
            rec.revenue_after_discount = revenue_after_discount
            rec.expenses_total = expenses
            rec.team_cost_total = team_cost
            rec.profit = profit
            rec.margin_net = margin_net

class ProjectFinancingRoleBreakdown(models.Model):
    _name = "project.financing.role.breakdown"
    _description = "Distribución por Rol"

    financing_id = fields.Many2one("project.financing", required=True, ondelete="cascade")
    role_id = fields.Many2one("project.role", required=True)
    hours = fields.Float(required=True)
    rate_id = fields.Many2one("project.role.rate", string="Tarifa")
    price_hour = fields.Monetary(related="rate_id.rate_hour", currency_field="currency_id", store=True, readonly=False)
    currency_id = fields.Many2one(related="financing_id.currency_id", store=True, readonly=True)
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True, currency_field="currency_id")

    @api.depends("hours", "price_hour")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = (rec.hours or 0.0) * (rec.price_hour or 0.0)

class ProjectFinancingCostLine(models.Model):
    _name = "project.financing.cost.line"
    _description = "Gasto/Servicio en USD"

    financing_id = fields.Many2one("project.financing", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    amount_usd = fields.Float(required=True)
    currency_id = fields.Many2one(related="financing_id.currency_id", store=True, readonly=True)
    usd_rate = fields.Float(related="financing_id.usd_rate", store=True, readonly=False)
    subtotal_converted = fields.Monetary(compute="_compute_converted", store=True, currency_field="currency_id")

    @api.depends("amount_usd", "usd_rate")
    def _compute_converted(self):
        for rec in self:
            rec.subtotal_converted = (rec.amount_usd or 0.0) * (rec.usd_rate or 1.0)

class ProjectFinancingEmployeeAllocation(models.Model):
    _name = "project.financing.employee.allocation"
    _description = "Asignación de Empleado"

    financing_id = fields.Many2one("project.financing", required=True, ondelete="cascade")
    employee_id = fields.Many2one("hr.employee", required=True)
    hours = fields.Float(required=True)
    hourly_cost_id = fields.Many2one("employee.hourly.cost", string="Costo por Hora")
    cost_hour = fields.Monetary(related="hourly_cost_id.cost_hour", currency_field="currency_id", store=True, readonly=False)
    currency_id = fields.Many2one(related="financing_id.currency_id", store=True, readonly=True)
    subtotal_cost = fields.Monetary(compute="_compute_subtotal", store=True, currency_field="currency_id")

    @api.depends("hours", "cost_hour")
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal_cost = (rec.hours or 0.0) * (rec.cost_hour or 0.0)