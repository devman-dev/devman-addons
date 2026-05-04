from odoo import api, fields, models


class PfGatewayBankAccount(models.Model):
    _name = "pf.gateway.bank.account"
    _description = "Cuenta bancaria de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    origin_id = fields.Integer(index=True)
    gateway_user_id = fields.Many2one("pf.gateway.user", string="Usuario del gateway", ondelete="set null", index=True)
    cvu_cbu = fields.Char(index=True)
    account_type = fields.Char()
    alias = fields.Char(index=True)
    status = fields.Char(index=True)
    is_primary = fields.Boolean()
    bdc_account_id = fields.Char(index=True)
    app = fields.Char(index=True)
    currency = fields.Char()
    balance = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Moneda de Odoo")
    extra_metadata = fields.Text()
    source_created_at = fields.Datetime()
    source_updated_at = fields.Datetime(index=True)
    last_sync_at = fields.Datetime(index=True)
    raw_payload = fields.Text()
    outgoing_transfer_ids = fields.One2many("pf.gateway.transfer", "source_bank_account_id", string="Transferencias salientes")
    incoming_transfer_ids = fields.One2many("pf.gateway.transfer", "destination_bank_account_id", string="Transferencias entrantes")
    user_display_name = fields.Char(
        string="Usuario",
        compute="_compute_user_display_name",
        store=False,
    )

    _sql_constraints = [
        ("pf_gateway_bank_account_external_id_uniq", "unique(external_id)", "El external_id de la cuenta bancaria del gateway debe ser único."),
    ]

    @api.depends("cvu_cbu", "alias", "origin_id")
    def _compute_name(self):
        for record in self:
            record.name = record.cvu_cbu or record.alias or str(record.origin_id or record.external_id)

    def _resolve_currency(self, currency_code):
        if not currency_code:
            return False
        return self.env["res.currency"].search([("name", "=", currency_code)], limit=1).id

    def action_sync_bank_accounts(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar cuentas bancarias ({sync_mode})",
                "resource": "bank_accounts",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get("/admin/gateway/bank-accounts", updated_since=updated_since)
            for item in items:
                gateway_user = self.env["pf.gateway.user"].search([("external_id", "=", item.get("user_id"))], limit=1)
                values = {
                    "external_id": item.get("id"),
                    "active": True,
                    "origin_id": item.get("origin_id"),
                    "gateway_user_id": gateway_user.id,
                    "cvu_cbu": item.get("cvu_cbu"),
                    "account_type": item.get("account_type"),
                    "alias": item.get("alias"),
                    "status": item.get("status"),
                    "is_primary": item.get("is_primary", False),
                    "bdc_account_id": item.get("bdc_account_id"),
                    "app": item.get("app"),
                    "currency": item.get("currency"),
                    "currency_id": self._resolve_currency(item.get("currency")),
                    "balance": item.get("balance") or 0.0,
                    "extra_metadata": self._payload_to_text(item.get("extra_metadata")),
                    "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
                    "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self._payload_to_text(item),
                }
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if record:
                    record.write(values)
                else:
                    self.create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Cuentas Bancarias sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de cuentas bancarias fallo.",
                }
            )
            if job:
                job.write(
                    {
                        "last_run_at": fields.Datetime.now(),
                        "last_status": "failed",
                        "last_message": str(exc),
                    }
                )
            raise

    def _compute_user_display_name(self):
        for record in self:
            user = record.gateway_user_id
            record.user_display_name = user.full_name or user.name or user.email or user.external_id or "-"

    def name_get(self):
        result = []
        for record in self:
            user = record.gateway_user_id
            user_name = user.full_name or user.name or user.email or user.external_id or "-"
            label = f"{user_name} - {record.cvu_cbu}" if record.cvu_cbu else user_name
            result.append((record.id, label))
        return result

