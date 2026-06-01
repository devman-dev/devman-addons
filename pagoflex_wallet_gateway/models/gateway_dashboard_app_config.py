from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PfGatewayDashboardAppConfig(models.Model):
    _name = "pf.gateway.dashboard.app.config"
    _description = "Configuracion de billetera para Centro de Control"
    _order = "sequence, app_name, id"

    name = fields.Char(compute="_compute_name", store=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    app_name = fields.Char(string="App", required=True, index=True)
    commission_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta de comisiones",
        ondelete="set null",
        domain="[('status', '=', 'active')]",
        index=True,
    )

    _sql_constraints = [
        (
            "pf_gateway_dashboard_app_config_app_uniq",
            "unique(app_name)",
            "La app debe tener una unica configuracion para el Centro de Control.",
        ),
    ]

    @api.depends("app_name")
    def _compute_name(self):
        for record in self:
            record.name = record._display_app_name(record.app_name)

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("app_name"):
                values["app_name"] = self._normalize_app_name(values["app_name"])
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("app_name"):
            vals["app_name"] = self._normalize_app_name(vals["app_name"])
        return super().write(vals)

    @api.constrains("app_name")
    def _check_normalized_app_name_unique(self):
        for record in self:
            app_key = record._normalize_app_name(record.app_name)
            duplicates = self.search([("id", "!=", record.id), ("app_name", "!=", False)])
            for duplicate in duplicates:
                if duplicate._normalize_app_name(duplicate.app_name) == app_key:
                    raise ValidationError(_("Ya existe una configuracion para la app %s.") % record._display_app_name(app_key))

    @api.model
    def _normalize_app_name(self, app_name):
        return (app_name or "").strip().lower()

    @api.model
    def _display_app_name(self, app_name):
        value = (app_name or "").strip()
        known = {
            "pagoflex": "PagoFlex",
            "sivep": "SIVEP",
        }
        return known.get(value.lower(), value or "-")
