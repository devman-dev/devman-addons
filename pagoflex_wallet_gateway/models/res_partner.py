from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_gateway_commission_agent = fields.Boolean(string="Es comisionista PagoFlex")
    gateway_commission_agent_code = fields.Char(string="Código de comisionista PagoFlex", index=True)
    gateway_min_commission_percentage = fields.Float(
        string="Porcentaje mínimo de comisión PagoFlex",
        digits=(16, 4),
        default=0.0,
    )
    gateway_user_ids = fields.One2many("pf.gateway.user", "partner_id", string="Usuarios gateway")
    gateway_company_ids = fields.One2many("pf.gateway.company", "partner_id", string="Cuentas empresas gateway")
    gateway_company_commission_line_ids = fields.One2many(
        "pf.gateway.company.commission.agent",
        "agent_partner_id",
        string="Reglas de comisión PagoFlex",
    )
    gateway_commission_agent_line_ids = fields.One2many(
        "pf.gateway.company.commission.agent",
        "company_partner_id",
        string="Comisionistas PagoFlex",
    )
    gateway_commission_agent_total_percentage = fields.Float(
        string="Total comisionistas PagoFlex",
        compute="_compute_gateway_commission_agent_total_percentage",
        digits=(16, 4),
    )

    @api.depends("gateway_commission_agent_line_ids.percentage", "gateway_commission_agent_line_ids.active")
    def _compute_gateway_commission_agent_total_percentage(self):
        for partner in self:
            partner.gateway_commission_agent_total_percentage = sum(
                partner.gateway_commission_agent_line_ids.filtered("active").mapped("percentage")
            )

    _sql_constraints = [
        (
            "res_partner_gateway_commission_agent_code_uniq",
            "unique(gateway_commission_agent_code)",
            "El código de comisionista PagoFlex debe ser único.",
        ),
        (
            "res_partner_gateway_min_commission_percentage_non_negative",
            "check(gateway_min_commission_percentage >= 0)",
            "El porcentaje mínimo de comisión PagoFlex no puede ser negativo.",
        ),
    ]
