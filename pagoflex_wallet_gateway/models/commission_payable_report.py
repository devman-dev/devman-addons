from odoo import fields, models, tools


class PfGatewayCommissionPayableReport(models.Model):
    _name = "pf.gateway.commission.payable.report"
    _description = "Reporte de comisiones a abonar"
    _auto = False
    _order = "month desc, company_id, agent_partner_id"

    month = fields.Date(string="Mes", readonly=True)
    company_id = fields.Many2one("pf.gateway.company", string="Empresa", readonly=True)
    company_partner_id = fields.Many2one("res.partner", string="Contacto empresa", readonly=True)
    agent_partner_id = fields.Many2one("res.partner", string="Comisionista", readonly=True)
    agent_code = fields.Char(string="Codigo", readonly=True)
    percentage = fields.Float(string="Porcentaje", digits=(16, 4), readonly=True, group_operator=False)
    transaction_count = fields.Integer(string="Total transacciones", readonly=True, group_operator=False)
    total_amount = fields.Float(string="Total importe", digits=(16, 2), readonly=True, group_operator=False)
    retained_commission = fields.Float(string="Comision retenida", digits=(16, 2), readonly=True, group_operator=False)
    commission_amount = fields.Float(string="Comision", digits=(16, 2), readonly=True)
    currency = fields.Char(string="Moneda", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)

        # Verificar que las tablas dependientes existen antes de crear la vista compleja.
        # En una instalación nueva el modulo puede inicializar los modelos en orden
        # alfabético y la tabla pf_gateway_company_commission_gateway_agent puede no
        # existir todavía en ese momento. En ese caso creamos una vista vacía; Odoo
        # la recreará correctamente en el siguiente -u o reinicio.
        self.env.cr.execute(
            """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN (
                  'pf_gateway_company_commission_gateway_agent',
                  'pf_gateway_transfer',
                  'pf_gateway_company_membership',
                  'pf_gateway_company'
              )
            """
        )
        found_tables = self.env.cr.fetchone()[0]
        if found_tables < 4:
            # Crear vista vacía stub para no bloquear la instalación
            self.env.cr.execute(
                """
                CREATE OR REPLACE VIEW %s AS (
                    SELECT
                        0::integer AS id,
                        NULL::date AS month,
                        NULL::integer AS company_id,
                        NULL::integer AS company_partner_id,
                        NULL::integer AS agent_partner_id,
                        NULL::varchar AS agent_code,
                        0.0::double precision AS percentage,
                        0::integer AS transaction_count,
                        0.0::double precision AS total_amount,
                        0.0::double precision AS retained_commission,
                        0.0::double precision AS commission_amount,
                        NULL::varchar AS currency
                    WHERE false
                )
                """
                % self._table
            )
            return

        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                WITH company_rates AS (
                    SELECT
                        company_id,
                        SUM(commission_percentage) AS retained_percentage
                    FROM pf_gateway_company_commission_gateway_agent
                    WHERE is_active
                    GROUP BY company_id
                ),
                commission_lines AS (
                    SELECT
                        c.id AS company_id,
                        company_user.partner_id AS company_partner_id,
                        date_trunc('month', t.transaction_at)::date AS month,
                        agent_user.partner_id AS agent_partner_id,
                        agent.gateway_commission_agent_code AS agent_code,
                        cga.commission_percentage AS percentage,
                        t.id AS transfer_id,
                        t.amount AS amount,
                        t.currency AS currency,
                        COALESCE(account_commission.commission_percentage, company_rates.retained_percentage, 0.0) AS retained_percentage
                    FROM pf_gateway_transfer t
                    JOIN pf_gateway_company_membership membership
                        ON membership.active
                       AND membership.user_id = t.source_user_id
                       AND membership.company_id IS NOT NULL
                    JOIN pf_gateway_company c
                        ON c.id = membership.company_id
                    LEFT JOIN pf_gateway_user company_user
                        ON company_user.id = c.created_by_user_id
                    JOIN pf_gateway_company_commission_gateway_agent cga
                        ON cga.is_active
                       AND cga.company_id = c.id
                    LEFT JOIN pf_gateway_user agent_user
                        ON agent_user.id = cga.user_id
                    JOIN res_partner agent
                        ON agent.id = agent_user.partner_id
                    LEFT JOIN company_rates
                        ON company_rates.company_id = c.id
                    LEFT JOIN pf_gateway_bank_account source_account
                        ON source_account.id = t.source_bank_account_id
                    LEFT JOIN LATERAL (
                        SELECT commission.commission_percentage
                        FROM pf_gateway_incoming_transfer_commission_account commission
                        WHERE commission.active
                          AND commission.is_active
                          AND (
                                commission.cvu_cbu = source_account.cvu_cbu
                             OR commission.bank_account_external_id = source_account.external_id
                          )
                        ORDER BY commission.updated_at DESC NULLS LAST, commission.id DESC
                        LIMIT 1
                    ) account_commission ON TRUE
                    WHERE t.active
                      AND t.movement_nature = 'TRANSFER'
                      AND t.transaction_at IS NOT NULL
                ),
                grouped AS (
                    SELECT
                        company_id,
                        company_partner_id,
                        month,
                        agent_partner_id,
                        agent_code,
                        percentage,
                        COALESCE(currency, '') AS currency,
                        COUNT(DISTINCT transfer_id) AS transaction_count,
                        SUM(amount) AS total_amount,
                        SUM(amount * retained_percentage / 100.0) AS retained_commission,
                        SUM(amount * percentage / 100.0) AS commission_amount
                    FROM commission_lines
                    GROUP BY
                        company_id,
                        company_partner_id,
                        month,
                        agent_partner_id,
                        agent_code,
                        percentage,
                        COALESCE(currency, '')
                )
                SELECT
                    row_number() OVER (
                        ORDER BY month DESC, company_id, agent_partner_id, percentage, currency
                    )::integer AS id,
                    company_id,
                    company_partner_id,
                    month,
                    agent_partner_id,
                    agent_code,
                    percentage,
                    transaction_count::integer AS transaction_count,
                    total_amount,
                    retained_commission,
                    commission_amount,
                    NULLIF(currency, '') AS currency
                FROM grouped
            )
            """
            % self._table
        )
