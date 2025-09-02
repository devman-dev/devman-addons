from odoo import fields, models

class ResCompany(models.Model):
    _inherit = "res.company"

    exchange_account_buy_id = fields.Many2one(
        "account.account", string="Cuenta compra divisa"
    )
    exchange_account_buy_counterpart_id = fields.Many2one(
        "account.account", string="Cuenta contrapartida compra"
    )
    exchange_account_pay_id = fields.Many2one(
        "account.account", string="Cuenta pago divisa"
    )
    exchange_account_spread_income_id = fields.Many2one(
        "account.account", string="Cuenta ingreso spread"
    )
    exchange_account_pay_counterpart_id = fields.Many2one(
        "account.account", string="Cuenta contrapartida pago"
    )
    exchange_default_account_cash_id = fields.Many2one(
        "account.account", string="Cuenta Caja/Banco por defecto"
    )
    exchange_default_account_inventory_id = fields.Many2one(
        "account.account", string="Cuenta Inventario Divisa por defecto"
    )
    exchange_default_account_spread_income_id = fields.Many2one(
        "account.account", string="Cuenta Ingreso Spread por defecto"
    )
    exchange_default_account_spread_expense_id = fields.Many2one(
        "account.account", string="Cuenta Gasto Spread por defecto"
    )
    price_seller_default = fields.Float(
        string="Precio vendedor por defecto"
    )
    price_buyer_default = fields.Float(
        string="Precio comprador por defecto"
    )
