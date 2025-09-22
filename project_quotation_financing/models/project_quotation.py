# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ProjectQuotation(models.Model):
    _name = "project.quotation"
    _description = "Cotización de Proyecto"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Nombre", required=True, tracking=True)
    sequence = fields.Char(string="Secuencia", readonly=True, copy=False, default=lambda self: _("New"))
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True)
    lead_id = fields.Many2one("crm.lead", string="Oportunidad", required=True, ondelete="set null")
    line_ids = fields.One2many("project.quotation.line", "quotation_id", string="Líneas")
    total_hours = fields.Float(compute="_compute_totals", store=True)
    state = fields.Selection([("draft","Borrador"),("financing","Financiamiento"),("done","Hecho")], default="draft", tracking=True)
    note = fields.Text(string="Observaciones")

    def action_to_financing(self):
        for rec in self:
            financing = self.env["project.financing"].create({
                "quotation_id": rec.id,
                "partner_id": rec.partner_id.id,
                "lead_id": rec.lead_id.id,
                "team_id": False,
            })
            rec.state = "financing"
            action = self.env.ref("project_quotation_financing.action_project_financing").read()[0]
            action["res_id"] = financing.id
            action["view_mode"] = "form"
            return action

    @api.depends("line_ids.total_hours")
    def _compute_totals(self):
        for rec in self:
            rec.total_hours = sum(rec.line_ids.mapped("total_hours"))

    @api.model
    def create(self, vals):
        if vals.get("sequence", _("New")) == _("New"):
            vals["sequence"] = self.env["ir.sequence"].next_by_code("project.quotation") or _("New")
        return super().create(vals)

class ProjectQuotationLine(models.Model):
    _name = "project.quotation.line"
    _description = "Línea de Cotización"

    quotation_id = fields.Many2one("project.quotation", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Módulo/Servicio", required=True)
    complexity_id = fields.Many2one("project.complexity.ref", string="Complejidad")
    role_distribution_ids = fields.One2many("project.quotation.line.role", "line_id", string="Distribución de Roles")
    computed_hours = fields.Float(string="Horas Computadas")
    total_hours = fields.Float(compute="_compute_total_hours", store=True)

    @api.depends("computed_hours", "complexity_id.factor")
    def _compute_total_hours(self):
        for rec in self:
            base = rec.computed_hours or 0.0
            factor = rec.complexity_id.factor if rec.complexity_id else 1.0
            rec.total_hours = base * factor

class ProjectQuotationLineRole(models.Model):
    _name = "project.quotation.line.role"
    _description = "Distribución de Roles por Línea"

    line_id = fields.Many2one("project.quotation.line", required=True, ondelete="cascade")
    role_id = fields.Many2one("project.role", required=True)
    percent = fields.Float(string="% del Rol", help="Porcentaje de horas de la línea asignadas a este rol")