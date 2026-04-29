from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class PfGatewayNegativeBalanceLimit(models.Model):
    _name = "pf.gateway.negative.balance.limit"
    _description = "Limite de saldo negativo PagoFlex"
    _inherit = "pf.gateway.client.mixin"
    _order = "updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(string="ID gateway", index=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta bancaria", ondelete="set null", index=True)
    bank_account_external_id = fields.Char(string="ID cuenta bancaria", index=True)
    cvu_cbu = fields.Char(string="CVU/CBU", required=True, index=True)
    limit_amount = fields.Float(string="Limite", digits=(16, 2), required=True)
    is_active = fields.Boolean(string="Activo en gateway", default=True, index=True)
    created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Ultima sincronizacion", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_negative_balance_limit_external_id_uniq",
            "unique(external_id)",
            "El ID gateway del limite de saldo negativo debe ser unico.",
        ),
        (
            "pf_gateway_negative_balance_limit_cvu_cbu_uniq",
            "unique(cvu_cbu)",
            "El CVU/CBU del limite de saldo negativo debe ser unico.",
        ),
        (
            "pf_gateway_negative_balance_limit_amount_non_negative",
            "check(limit_amount >= 0)",
            "El limite de saldo negativo no puede ser negativo.",
        ),
    ]

    @api.depends("cvu_cbu", "limit_amount", "is_active")
    def _compute_name(self):
        for record in self:
            status = _("Activo") if record.is_active else _("Inactivo")
            record.name = "%s - %.2f (%s)" % (record.cvu_cbu or "", record.limit_amount or 0.0, status)

    @api.constrains("cvu_cbu")
    def _check_cvu_cbu(self):
        for record in self:
            if record.cvu_cbu and not record.cvu_cbu.strip():
                raise ValidationError(_("El CVU/CBU no puede estar vacio."))

    def _resolve_bank_account(self, cvu_cbu=None, bank_account_external_id=None):
        account = self.env["pf.gateway.bank.account"]
        if bank_account_external_id:
            account = account.search([("external_id", "=", str(bank_account_external_id))], limit=1)
        if not account and cvu_cbu:
            account = account.search([("cvu_cbu", "=", cvu_cbu)], limit=1)
        return account

    def _values_from_gateway_item(self, item):
        if not isinstance(item, dict):
            raise UserError(_("La respuesta del gateway contiene items invalidos."))

        cvu_cbu = item.get("cvu_cbu") or item.get("cvu") or item.get("cbu")
        bank_account_external_id = item.get("bank_account_id")
        bank_account = self._resolve_bank_account(cvu_cbu=cvu_cbu, bank_account_external_id=bank_account_external_id)
        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "active": True,
            "bank_account_id": bank_account.id,
            "bank_account_external_id": bank_account_external_id or False,
            "cvu_cbu": cvu_cbu,
            "limit_amount": float(item.get("limit_amount") or 0.0),
            "is_active": bool(item.get("is_active")),
            "created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _upsert_items(self, items):
        processed = 0
        for item in items or []:
            values = self._values_from_gateway_item(item)
            domain = []
            if values.get("external_id"):
                domain = [("external_id", "=", values["external_id"])]
            elif values.get("cvu_cbu"):
                domain = [("cvu_cbu", "=", values["cvu_cbu"])]
            record = self.search(domain, limit=1) if domain else self.browse()
            if record:
                record.write(values)
            else:
                self.create(values)
            processed += 1
        return processed

    def _gateway_payload(self):
        self.ensure_one()
        return {
            "cvu_cbu": self.cvu_cbu,
            "limit_amount": self.limit_amount,
            "is_active": bool(self.is_active),
        }

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if isinstance(payload, dict):
            item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
            item = dict(item)
            item.setdefault("cvu_cbu", self.cvu_cbu)
            item.setdefault("limit_amount", self.limit_amount)
            item.setdefault("is_active", self.is_active)
            item.setdefault("id", self.external_id)
            self.with_context(skip_negative_balance_limit_push=True).write(self._values_from_gateway_item(item))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_negative_balance_limit_push"):
            return records
        for record in records:
            record.action_push_to_gateway()
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_negative_balance_limit_push"):
            return result
        push_fields = {"cvu_cbu", "limit_amount", "is_active"}
        if push_fields.intersection(vals):
            for record in self:
                record.action_push_to_gateway()
        return result

    def action_push_to_gateway(self):
        for record in self:
            if not record.cvu_cbu:
                raise UserError(_("Configura un CVU/CBU antes de enviar el limite al gateway."))
            response = record._gateway_request_json(
                "PUT",
                "/admin/gateway/negative-balance-limits",
                payload=record._gateway_payload(),
            )
            record._update_from_gateway_payload(response)
        return True

    @api.model
    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None, limit=None, offset=0):
        page_limit = max(1, int(limit or self._gateway_page_size()))
        current_offset = max(0, int(offset or 0))
        processed = 0

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar limites de saldo negativo ({sync_mode})",
                "resource": "negative_balance_limits",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            while True:
                payload = self._gateway_request_json(
                    "GET",
                    "/admin/gateway/negative-balance-limits",
                    params={"limit": page_limit, "offset": current_offset},
                )
                items = payload.get("items") or []
                if not isinstance(items, list):
                    raise UserError(_("La respuesta del gateway no contiene una lista valida en 'items'."))

                processed += self.with_context(skip_negative_balance_limit_push=True)._upsert_items(items)
                total = int(payload.get("total") or 0)
                if not items:
                    break
                if current_offset + len(items) >= total:
                    break
                if len(items) < page_limit:
                    break
                current_offset += page_limit

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": processed,
                    "message": f"Limites de saldo negativo sincronizados: {processed}",
                }
            )
            return processed
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronizacion de limites de saldo negativo fallo.",
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

    def action_sync_from_gateway(self):
        processed = self.env["pf.gateway.negative.balance.limit"].sync_from_gateway()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Limites sincronizados"),
                "message": _("Se procesaron %s registros.") % processed,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
