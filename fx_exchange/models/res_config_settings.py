from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    fx_default_journal_id = fields.Many2one(
        "account.journal", string="Diario de caja por defecto",
        domain=[("type", "in", ("cash", "bank"))],
        config_parameter="fx_exchange.fx_default_journal_id",
    )
    fx_inventory_account_id = fields.Many2one(
        "account.account", string="Cuenta de efectivo en divisa (inventario)",
        config_parameter="fx_exchange.fx_inventory_account_id",
    )
    fx_income_account_id = fields.Many2one(
        "account.account", string="Cuenta de ingreso por spread",
        config_parameter="fx_exchange.fx_income_account_id",
    )
    fx_expense_account_id = fields.Many2one(
        "account.account", string="Cuenta de gasto por spread",
        config_parameter="fx_exchange.fx_expense_account_id",
    )
    fx_commission_product_id = fields.Many2one(
        "product.product", string="Producto comisión FX",
        help="Opcional: para facturar comisión; debe estar ligado a cuenta de ingreso."
    )
    fx_commission_percent = fields.Float(
        string="% Comisión por operación", default=0.0,
        config_parameter="fx_exchange.fx_commission_percent",
        help="Porcentaje sobre el importe en moneda compañía."
    )
    fx_block_negative_inventory = fields.Boolean(
        string="Bloquear inventario FX negativo",
        config_parameter="fx_exchange.fx_block_negative_inventory",
        default=True,
    )
