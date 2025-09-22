# -*- coding: utf-8 -*-
from odoo import api, fields, models

class ProjectQuotationSummary(models.Model):
    _name = "project.quotation.summary"
    _description = "Resumen de Cotización"

    quotation_id = fields.Many2one("project.quotation", required=True, ondelete="cascade")
    financing_id = fields.Many2one("project.financing", required=True, ondelete="cascade")
    lead_id = fields.Many2one("crm.lead", required=True)
    partner_id = fields.Many2one("res.partner", required=True)
    total_hours = fields.Float(related="quotation_id.total_hours", store=True)

    financing_type = fields.Selection(related="financing_id.financing_type", store=True)
    revenue = fields.Monetary(related="financing_id.revenue", store=True)
    revenue_after_discount = fields.Monetary(related="financing_id.revenue_after_discount", store=True)
    expenses_total = fields.Monetary(related="financing_id.expenses_total", store=True)
    team_cost_total = fields.Monetary(related="financing_id.team_cost_total", store=True)
    profit = fields.Monetary(related="financing_id.profit", store=True)
    margin_net = fields.Float(related="financing_id.margin_net", store=True)
    currency_id = fields.Many2one(related="financing_id.currency_id", store=True)

    observations = fields.Text()

    def action_print_pdf(self):
        return self.env.ref("project_quotation_financing.action_report_project_summary").report_action(self)