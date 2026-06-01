from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pagoflex_gateway_base_url = fields.Char(
        string="URL Base del Gateway",
        config_parameter="pagoflex_wallet_gateway.base_url",
    )
    pagoflex_gateway_api_key = fields.Char(
        string="API Key del Gateway",
        config_parameter="pagoflex_wallet_gateway.api_key",
    )
    pagoflex_gateway_timeout_seconds = fields.Integer(
        string="Timeout (segundos)",
        config_parameter="pagoflex_wallet_gateway.timeout_seconds",
        default=20,
    )
    pagoflex_gateway_page_size = fields.Integer(
        string="Tamano de pagina",
        config_parameter="pagoflex_wallet_gateway.page_size",
        default=200,
    )
    pagoflex_gateway_verify_ssl = fields.Boolean(
        string="Verificar SSL",
        config_parameter="pagoflex_wallet_gateway.verify_ssl",
        default=True,
    )
    pagoflex_gateway_membership_owner_cuit = fields.Char(
        string="CUIT owner para membresias",
        config_parameter="pagoflex_wallet_gateway.membership_owner_cuit",
    )
    pagoflex_gateway_membership_is_active = fields.Selection(
        [
            ("", "Todas"),
            ("true", "Solo activas"),
            ("false", "Solo inactivas"),
        ],
        string="Filtro activo membresias",
        config_parameter="pagoflex_wallet_gateway.membership_is_active",
        default="",
    )
    pagoflex_gateway_bank_movement_query_cbu = fields.Char(
        string="CBU/CVU/Alias fijo para movimientos",
        config_parameter="pagoflex_wallet_gateway.bank_movement_query_cbu",
    )
    pagoflex_gateway_completed_business_data_batch_size = fields.Integer(
        string="Tamano lote datos bancarios",
        config_parameter="pagoflex_wallet_gateway.completed_business_data_batch_size",
        default=50,
    )
