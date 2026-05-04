from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero


class PfGatewayCompanyCommissionAgent(models.Model):
    _name = "pf.gateway.company.commission.agent"
    _description = "Comisionista por empresa PagoFlex"
    _order = "company_partner_id, sequence, id"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    company_gateway_user_id = fields.Many2one(
        "pf.gateway.user",
        string="Empresa gateway",
        ondelete="set null",
        index=True,
        domain=[("partner_is_company", "=", True)],
    )
    company_partner_id = fields.Many2one(
        "res.partner",
        string="Contacto empresa",
        required=True,
        ondelete="cascade",
        index=True,
        domain=[("is_company", "=", True)],
    )
    agent_partner_id = fields.Many2one(
        "res.partner",
        string="Comisionista",
        required=True,
        ondelete="restrict",
        index=True,
        domain=[("is_gateway_commission_agent", "=", True)],
    )
    agent_code = fields.Char(related="agent_partner_id.gateway_commission_agent_code", string="Código", readonly=True)
    percentage = fields.Float(string="Porcentaje", required=True, digits=(16, 4))
    company_total_percentage = fields.Float(
        string="Total asignado",
        compute="_compute_company_total_percentage",
        digits=(16, 4),
    )
    max_percentage = fields.Float(
        string="Máximo permitido",
        compute="_compute_max_percentage",
        digits=(16, 4),
    )

    _sql_constraints = [
        (
            "pf_gateway_company_commission_agent_uniq",
            "unique(company_gateway_user_id, agent_partner_id)",
            "Cada comisionista puede cargarse una sola vez por empresa.",
        ),
        (
            "pf_gateway_company_commission_agent_partner_uniq",
            "unique(company_partner_id, agent_partner_id)",
            "Cada comisionista puede cargarse una sola vez por empresa.",
        ),
        (
            "pf_gateway_company_commission_agent_percentage_non_negative",
            "check(percentage >= 0)",
            "El porcentaje de comisión no puede ser negativo.",
        ),
    ]

    @api.depends("company_partner_id.gateway_commission_agent_line_ids.percentage", "company_partner_id.gateway_commission_agent_line_ids.active")
    def _compute_company_total_percentage(self):
        totals = {}
        for company in self.mapped("company_partner_id"):
            totals[company.id] = sum(company.gateway_commission_agent_line_ids.filtered("active").mapped("percentage"))
        for record in self:
            record.company_total_percentage = totals.get(record.company_partner_id.id, 0.0)

    def _commission_settings(self):
        return self.env["pf.gateway.incoming.transfer.commission.settings"].search(
            [
                "|",
                ("app_name", "!=", False),
                ("gateway_setting_id", "!=", False),
            ],
            order="is_active desc, id",
            limit=1,
        )

    @api.depends("company_partner_id")
    def _compute_max_percentage(self):
        settings = self._commission_settings()
        max_percentage = settings.default_percentage if settings else 0.0
        for record in self:
            record.max_percentage = max_percentage

    @api.constrains("company_partner_id", "company_gateway_user_id")
    def _check_company(self):
        for record in self:
            if record.company_partner_id and not record.company_partner_id.is_company:
                raise ValidationError(_("El contacto empresa debe estar marcado como compañía."))
            if record.company_gateway_user_id and record.company_gateway_user_id.partner_id != record.company_partner_id:
                raise ValidationError(_("La empresa gateway debe estar vinculada al mismo contacto empresa de la regla."))

    @api.constrains("agent_partner_id")
    def _check_agent_partner(self):
        for record in self:
            if record.agent_partner_id and not record.agent_partner_id.is_gateway_commission_agent:
                raise ValidationError(_("El contacto seleccionado debe estar marcado como comisionista PagoFlex."))

    @api.constrains("agent_partner_id", "percentage")
    def _check_minimum_percentage(self):
        for record in self.filtered("active"):
            minimum = record.agent_partner_id.gateway_min_commission_percentage
            if minimum and float_compare(record.percentage, minimum, precision_digits=4) < 0:
                raise ValidationError(
                    _("%(agent)s no puede tener un porcentaje menor a %(minimum).4f%%.")
                    % {
                        "agent": record.agent_partner_id.display_name,
                        "minimum": minimum,
                    }
                )

    @api.constrains("company_partner_id", "percentage", "active")
    def _check_company_total_percentage(self):
        settings = self._commission_settings()
        max_percentage = settings.default_percentage if settings else 0.0
        companies = self.mapped("company_partner_id")
        for company in companies:
            total = sum(company.gateway_commission_agent_line_ids.filtered("active").mapped("percentage"))
            if float_compare(total, max_percentage, precision_digits=4) > 0:
                raise ValidationError(
                    _("Los comisionistas de %(company)s suman %(total).4f%% y superan el máximo permitido de %(max).4f%%.")
                    % {
                        "company": company.display_name,
                        "total": total,
                        "max": max_percentage,
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._complete_company_gateway_user_values(vals)
        records = super().create(vals_list)
        records._ensure_non_zero_default_for_minimums()
        return records

    def write(self, vals):
        vals = dict(vals)
        self._complete_company_gateway_user_values(vals)
        result = super().write(vals)
        self._ensure_non_zero_default_for_minimums()
        return result

    def _complete_company_gateway_user_values(self, vals):
        if vals.get("company_gateway_user_id") and not vals.get("company_partner_id"):
            gateway_user = self.env["pf.gateway.user"].browse(vals["company_gateway_user_id"])
            if gateway_user.partner_id:
                vals["company_partner_id"] = gateway_user.partner_id.id
            return
        if vals.get("company_gateway_user_id") or not vals.get("company_partner_id"):
            return
        gateway_user = self.env["pf.gateway.user"].search(
            [("partner_id", "=", vals["company_partner_id"]), ("partner_is_company", "=", True)],
            limit=1,
        )
        if gateway_user:
            vals["company_gateway_user_id"] = gateway_user.id

    def _ensure_non_zero_default_for_minimums(self):
        active_lines = self.filtered("active")
        if not active_lines:
            return
        settings = self._commission_settings()
        if not settings:
            return
        required_minimum = max(active_lines.mapped("agent_partner_id.gateway_min_commission_percentage") or [0.0])
        if required_minimum and float_is_zero(settings.default_percentage, precision_digits=4):
            raise ValidationError(
                _("El porcentaje por defecto de comisión debe ser mayor a cero para cargar comisionistas con mínimo obligatorio.")
            )
