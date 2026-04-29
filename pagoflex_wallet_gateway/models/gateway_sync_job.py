from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewaySyncJob(models.Model):
    _name = "pf.gateway.sync.job"
    _description = "Trabajo de Sincronización de PagoFlex Gateway"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    resource = fields.Selection(
        [
            ("users", "Usuarios"),
            ("companies", "Empresas"),
            ("company_memberships", "Membresias"),
            ("bank_accounts", "Cuentas Bancarias"),
            ("negative_balance_limits", "Limites de Saldo Negativo"),
            ("transfers", "Transferencias"),
        ],
        required=True,
        index=True,
    )
    sync_mode = fields.Selection(
        [
            ("incremental", "Incremental"),
            ("full", "Completo"),
        ],
        default="incremental",
        required=True,
    )
    last_run_at = fields.Datetime(readonly=True)
    last_status = fields.Selection(
        [
            ("never", "Nunca"),
            ("success", "Exitoso"),
            ("failed", "Fallido"),
        ],
        default="never",
        readonly=True,
    )
    last_message = fields.Text(readonly=True)
    log_ids = fields.One2many("pf.gateway.sync.log", "job_id", string="Logs")

    def _resource_model(self, resource):
        resource_key = (resource or "").strip()
        model_map = {
            "users": self.env["pf.gateway.user"],
            "companies": self.env["pf.gateway.company"],
            "company_memberships": self.env["pf.gateway.company.membership"],
            "bank_accounts": self.env["pf.gateway.bank.account"],
            "negative_balance_limits": self.env["pf.gateway.negative.balance.limit"],
            "transfers": self.env["pf.gateway.transfer"],
        }
        model = model_map.get(resource_key)
        if model is None:
            raise UserError(_("Recurso de sincronizacion no soportado: %s") % resource)
        return model

    @api.model
    def _run_named_job(self, resource, cron_mode=True):
        job = self.search([("resource", "=", resource), ("active", "=", True)], limit=1)
        sync_mode = job.sync_mode if job else "incremental"
        mode = "cron" if cron_mode else "manual"
        processed = self._resource_model(resource).sync_from_gateway(mode=mode, sync_mode=sync_mode, job=job)
        if job:
            job.write(
                {
                    "last_run_at": fields.Datetime.now(),
                    "last_status": "success",
                    "last_message": f"{processed} registros procesados.",
                }
            )
        return processed

    def action_run_now(self):
        total_processed = 0
        for job in self:
            processed = self._resource_model(job.resource).sync_from_gateway(mode="manual", sync_mode=job.sync_mode, job=job)
            job.write(
                {
                    "last_run_at": fields.Datetime.now(),
                    "last_status": "success",
                    "last_message": f"{processed} registros procesados.",
                }
            )
            total_processed += processed

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronizacion completada"),
                "message": _("Se procesaron %s registros en total.") % total_processed,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def cron_sync_users(self):
        return self._run_named_job("users", cron_mode=True)

    @api.model
    def cron_sync_companies(self):
        return self._run_named_job("companies", cron_mode=True)

    @api.model
    def cron_sync_company_memberships(self):
        return self._run_named_job("company_memberships", cron_mode=True)

    @api.model
    def cron_sync_bank_accounts(self):
        return self._run_named_job("bank_accounts", cron_mode=True)

    @api.model
    def cron_sync_negative_balance_limits(self):
        return self._run_named_job("negative_balance_limits", cron_mode=True)

    @api.model
    def cron_sync_transfers(self):
        return self._run_named_job("transfers", cron_mode=True)
