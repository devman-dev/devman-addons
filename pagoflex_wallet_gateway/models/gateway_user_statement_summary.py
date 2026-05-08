from odoo import fields, models, tools


class PfGatewayUserStatementSummary(models.Model):
    _name = "pf.gateway.user.statement.summary"
    _description = "Resumen de cuenta por CVU y app PagoFlex"
    _auto = False
    _order = "app, cvu_cbu, id"

    user_id = fields.Many2one("pf.gateway.user", string="Usuario", readonly=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta", readonly=True)
    cvu_cbu = fields.Char(string="CVU/CBU", readonly=True)
    app = fields.Char(string="App", readonly=True)
    currency = fields.Char(string="Moneda", readonly=True)
    movement_count = fields.Integer(string="Movimientos", readonly=True)
    incoming_total = fields.Float(string="Entradas", digits=(16, 2), readonly=True)
    outgoing_total = fields.Float(string="Salidas", digits=(16, 2), readonly=True)
    net_total = fields.Float(string="Neto", digits=(16, 2), readonly=True)
    current_balance = fields.Float(string="Saldo cuenta", digits=(16, 2), readonly=True)
    control_difference = fields.Float(string="Diferencia control", digits=(16, 2), readonly=True)
    last_movement_at = fields.Datetime(string="Ultimo movimiento", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(line.id) AS id,
                    line.user_id AS user_id,
                    line.bank_account_id AS bank_account_id,
                    line.cvu_cbu AS cvu_cbu,
                    line.app AS app,
                    COALESCE(account.currency, MIN(line.currency)) AS currency,
                    COUNT(*) AS movement_count,
                    SUM(CASE WHEN line.signed_amount > 0 THEN line.signed_amount ELSE 0.0 END) AS incoming_total,
                    SUM(CASE WHEN line.signed_amount < 0 THEN -line.signed_amount ELSE 0.0 END) AS outgoing_total,
                    SUM(line.signed_amount) AS net_total,
                    COALESCE(account.balance, 0.0) AS current_balance,
                    SUM(line.signed_amount) - COALESCE(account.balance, 0.0) AS control_difference,
                    MAX(line.transaction_at) AS last_movement_at
                FROM pf_gateway_user_statement_line line
                LEFT JOIN pf_gateway_bank_account account
                    ON account.id = line.bank_account_id
                WHERE line.user_id IS NOT NULL
                    AND line.bank_account_id IS NOT NULL
                GROUP BY
                    line.user_id,
                    line.bank_account_id,
                    line.cvu_cbu,
                    line.app,
                    account.currency,
                    account.balance
            )
            """
        )
