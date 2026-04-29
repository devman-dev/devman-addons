from odoo import fields, models


class PfGatewaySyncLog(models.Model):
    _name = "pf.gateway.sync.log"
    _description = "Log de Sincronización de PagoFlex Gateway"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True)
    resource = fields.Selection(
        [
            ("users", "Usuarios"),
            ("companies", "Empresas"),
            ("company_memberships", "Membresias"),
            ("bank_accounts", "Cuentas Bancarias"),
            ("negative_balance_limits", "Limites de Saldo Negativo"),
            ("transfers", "Transferencias"),
            ("all", "Todo"),
        ],
        required=True,
        index=True,
    )
    mode = fields.Selection(
        [
            ("manual", "Manual"),
            ("cron", "Cron"),
        ],
        required=True,
        default="manual",
        index=True,
    )
    status = fields.Selection(
        [
            ("running", "En Ejecución"),
            ("success", "Exitoso"),
            ("failed", "Fallido"),
        ],
        required=True,
        default="running",
        index=True,
    )
    started_at = fields.Datetime(required=True, default=fields.Datetime.now)
    finished_at = fields.Datetime()
    records_processed = fields.Integer(default=0)
    job_id = fields.Many2one("pf.gateway.sync.job", string="Trabajo de Sincronización", ondelete="set null")
    message = fields.Text()
    error_detail = fields.Text()
