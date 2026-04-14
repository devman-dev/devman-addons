from odoo import fields, models


class CasinoApiProvider(models.Model):
    _name = "casino.api.provider"
    _description = "Casino API Provider"
    _order = "code"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    supports_round_close = fields.Boolean(default=False)
    supports_reversal = fields.Boolean(default=False)
    require_round_id_for_stake = fields.Boolean(default=False)
    require_round_id_for_payout = fields.Boolean(default=False)
    duplicate_window_sec = fields.Integer(default=259200)
    legacy_mode = fields.Selection(
        [
            ("transitional", "Transitional"),
            ("native", "Native"),
        ],
        default="transitional",
        required=True,
    )
    notes = fields.Text()

    _sql_constraints = [
        ("casino_api_provider_code_uniq", "unique(code)", "El codigo del proveedor debe ser unico."),
    ]
