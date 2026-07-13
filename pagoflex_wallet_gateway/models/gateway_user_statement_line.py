from odoo import fields, models, tools


class PfGatewayUserStatementLine(models.Model):
    _name = "pf.gateway.user.statement.line"
    _description = "Movimiento de resumen de cuenta por usuario PagoFlex"
    _auto = False
    _order = "transaction_at desc, id desc"

    user_id = fields.Many2one("pf.gateway.user", string="Usuario", readonly=True)
    transfer_id = fields.Many2one("pf.gateway.transfer", string="Transferencia", readonly=True)
    adjustment_id = fields.Many2one("pagoflex.balance.adjustment", string="Ajuste", readonly=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta", readonly=True)
    cvu_cbu = fields.Char(string="CVU/CBU", readonly=True)
    app = fields.Char(string="App", readonly=True)
    transaction_at = fields.Datetime(string="Fecha", readonly=True)
    name = fields.Char(string="Referencia", readonly=True)
    origin_id = fields.Char(string="Origin ID", readonly=True)
    payment_id = fields.Char(string="Payment ID", readonly=True)
    movement_nature = fields.Selection(
        [
            ("TRANSFER", "Transferencia"),
            ("COMMISSION", "Comision"),
            ("ADJUSTMENT", "Ajuste"),
        ],
        string="Tipo",
        readonly=True,
    )
    status = fields.Char(string="Estado", readonly=True)
    direction = fields.Selection(
        [
            ("incoming", "Entrada"),
            ("outgoing", "Salida"),
            ("internal", "Interno"),
        ],
        string="Sentido",
        readonly=True,
    )
    source_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta origen", readonly=True)
    destination_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta destino", readonly=True)
    counterparty_user_id = fields.Many2one("pf.gateway.user", string="Contraparte", readonly=True)
    counterparty_name = fields.Char(string="Nombre contraparte", readonly=True)
    amount = fields.Float(string="Importe", digits=(16, 2), readonly=True)
    signed_amount = fields.Float(string="Importe firmado", digits=(16, 2), readonly=True)
    running_balance = fields.Float(string="Saldo acumulado", digits=(16, 2), readonly=True)
    currency = fields.Char(string="Moneda", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH movement_lines AS (
                    SELECT
                        transfer.id * 10 + 1 AS id,
                        transfer.source_user_id AS user_id,
                        transfer.id AS transfer_id,
                        NULL::integer AS adjustment_id,
                        transfer.source_bank_account_id AS bank_account_id,
                        source_account.cvu_cbu AS cvu_cbu,
                        source_account.app AS app,
                        transfer.transaction_at::timestamp without time zone AS transaction_at,
                        transfer.name AS name,
                        transfer.origin_id AS origin_id,
                        transfer.payment_id AS payment_id,
                        transfer.movement_nature AS movement_nature,
                        transfer.status AS status,
                        CASE
                            WHEN transfer.source_user_id = transfer.destination_user_id THEN 'internal'
                            ELSE 'outgoing'
                        END AS direction,
                        transfer.source_bank_account_id AS source_bank_account_id,
                        transfer.destination_bank_account_id AS destination_bank_account_id,
                        CASE
                            WHEN transfer.source_user_id = transfer.destination_user_id THEN NULL
                            ELSE transfer.destination_user_id
                        END AS counterparty_user_id,
                        transfer.destination_owner_name AS counterparty_name,
                        transfer.amount AS amount,
                        CASE
                            WHEN transfer.status NOT IN ('CREATED', 'AUTHORIZED', 'CAPTURED', 'COMPLETED') THEN 0.0
                            ELSE -transfer.amount
                        END AS signed_amount,
                        transfer.currency AS currency
                    FROM pf_gateway_transfer transfer
                    LEFT JOIN pf_gateway_bank_account source_account
                        ON source_account.id = transfer.source_bank_account_id
                    WHERE transfer.source_user_id IS NOT NULL

                    UNION ALL

                    SELECT
                        transfer.id * 10 + 2 AS id,
                        transfer.destination_user_id AS user_id,
                        transfer.id AS transfer_id,
                        NULL::integer AS adjustment_id,
                        transfer.destination_bank_account_id AS bank_account_id,
                        destination_account.cvu_cbu AS cvu_cbu,
                        destination_account.app AS app,
                        transfer.transaction_at::timestamp without time zone AS transaction_at,
                        transfer.name AS name,
                        transfer.origin_id AS origin_id,
                        transfer.payment_id AS payment_id,
                        transfer.movement_nature AS movement_nature,
                        transfer.status AS status,
                        CASE
                            WHEN transfer.source_user_id = transfer.destination_user_id THEN 'internal'
                            ELSE 'incoming'
                        END AS direction,
                        transfer.source_bank_account_id AS source_bank_account_id,
                        transfer.destination_bank_account_id AS destination_bank_account_id,
                        transfer.source_user_id AS counterparty_user_id,
                        transfer.source_owner_name AS counterparty_name,
                        transfer.amount AS amount,
                        CASE
                            WHEN transfer.status NOT IN ('CAPTURED', 'COMPLETED') THEN 0.0
                            ELSE transfer.amount
                        END AS signed_amount,
                        transfer.currency AS currency
                    FROM pf_gateway_transfer transfer
                    LEFT JOIN pf_gateway_bank_account destination_account
                        ON destination_account.id = transfer.destination_bank_account_id
                    WHERE transfer.destination_user_id IS NOT NULL

                    UNION ALL

                    SELECT
                        adjustment.id * 10 + 3 AS id,
                        account.gateway_user_id AS user_id,
                        NULL::integer AS transfer_id,
                        adjustment.id AS adjustment_id,
                        adjustment.account_id AS bank_account_id,
                        account.cvu_cbu AS cvu_cbu,
                        account.app AS app,
                        COALESCE(
                            adjustment.write_date,
                            adjustment.create_date,
                            NOW() AT TIME ZONE 'UTC'
                        )::timestamp without time zone AS transaction_at,
                        adjustment.name AS name,
                        COALESCE(adjustment.gateway_adjustment_id, adjustment.idempotency_key, adjustment.external_reference, adjustment.name) AS origin_id,
                        adjustment.idempotency_key AS payment_id,
                        'ADJUSTMENT' AS movement_nature,
                        UPPER(adjustment.state) AS status,
                        CASE
                            WHEN adjustment.direction = 'credit' THEN 'incoming'
                            ELSE 'outgoing'
                        END AS direction,
                        CASE
                            WHEN adjustment.direction = 'debit' THEN adjustment.account_id
                            ELSE NULL::integer
                        END AS source_bank_account_id,
                        CASE
                            WHEN adjustment.direction = 'credit' THEN adjustment.account_id
                            ELSE NULL::integer
                        END AS destination_bank_account_id,
                        NULL::integer AS counterparty_user_id,
                        COALESCE(adjustment.description, 'Ajuste de saldo') AS counterparty_name,
                        adjustment.amount AS amount,
                        CASE
                            WHEN adjustment.state <> 'synced' THEN 0.0
                            WHEN adjustment.direction = 'credit' THEN adjustment.amount
                            ELSE -adjustment.amount
                        END AS signed_amount,
                        account.currency AS currency
                    FROM pagoflex_balance_adjustment adjustment
                    LEFT JOIN pf_gateway_bank_account account
                        ON account.id = adjustment.account_id
                    WHERE adjustment.account_id IS NOT NULL
                        AND adjustment.state = 'synced'
                )
                SELECT
                    movement_lines.*,
                    SUM(movement_lines.signed_amount) OVER (
                        PARTITION BY movement_lines.user_id, movement_lines.bank_account_id
                        ORDER BY movement_lines.transaction_at, movement_lines.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    ) AS running_balance
                FROM movement_lines
            )
            """
        )
