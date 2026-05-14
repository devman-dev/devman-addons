import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PfGatewayIncomingTransferCommissionAccount(models.Model):
    _name = "pf.gateway.incoming.transfer.commission.account"
    _description = "Comisión de transferencias entrantes por cuenta"
    _inherit = "pf.gateway.client.mixin"
    _order = "updated_at desc, id desc"
    _gateway_push_fields = {"commission_percentage", "is_active"}

    name = fields.Char(compute="_compute_name", store=True)
    user_display_name = fields.Char(
        string="Usuario",
        compute="_compute_user_display_name",
        store=False,
    )
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    bank_account_external_id = fields.Char(string="ID cuenta bancaria", index=True)
    cvu_cbu = fields.Char(string="CVU/CBU", index=True)
    commission_percentage = fields.Float(string="Porcentaje de comisión", digits=(16, 2))
    is_active = fields.Boolean(string="Activo", default=True, index=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(index=True, readonly=True)
    last_sync_at = fields.Datetime(index=True, readonly=True)
    raw_payload = fields.Text()

    _sql_constraints = [
        (
            "pf_gateway_incoming_transfer_commission_account_external_id_uniq",
            "unique(external_id)",
            "El identificador externo de la comisión por cuenta debe ser único.",
        ),
    ]

    @api.depends("cvu_cbu", "external_id")
    def _compute_name(self):
        for record in self:
            record.name = record.cvu_cbu or str(record.external_id)

    @api.depends("bank_account_external_id", "cvu_cbu")
    def _compute_user_display_name(self):
        account_model = self.env["pf.gateway.bank.account"]
        external_ids = list({r.bank_account_external_id for r in self if r.bank_account_external_id})
        cvu_values = list({r.cvu_cbu for r in self if r.cvu_cbu})

        accounts_by_external = {}
        accounts_by_cvu = {}

        if external_ids:
            for account in account_model.search([("external_id", "in", external_ids)]):
                if account.external_id and account.external_id not in accounts_by_external:
                    accounts_by_external[account.external_id] = account

        if cvu_values:
            for account in account_model.search([("cvu_cbu", "in", cvu_values)]):
                if account.cvu_cbu and account.cvu_cbu not in accounts_by_cvu:
                    accounts_by_cvu[account.cvu_cbu] = account

        for record in self:
            account = accounts_by_external.get(record.bank_account_external_id) or accounts_by_cvu.get(record.cvu_cbu)
            record.user_display_name = account.gateway_user_id.display_name if account and account.gateway_user_id else False

    def write(self, vals):
        should_push = (
            bool(self._gateway_push_fields.intersection(vals.keys()))
            and not self.env.context.get("skip_gateway_push")
            and not self.env.context.get("install_mode")
        )
        result = super().write(vals)
        if should_push:
            for record in self.filtered(lambda r: r._is_gateway_payload_ready()):
                record._push_to_gateway()
        return result

    def _is_gateway_payload_ready(self):
        self.ensure_one()
        return bool(self.cvu_cbu)

    def _push_to_gateway(self):
        self.ensure_one()
        app_name = self._get_app_name()
        payload = {
            "cvu_cbu": self.cvu_cbu,
            "commission_percentage": round(self.commission_percentage or 0.0, 2),
            "is_active": self.is_active,
        }
        response = self._gateway_request_json(
            "POST",
            "/admin/gateway/incoming-transfer-commission/accounts",
            params={"app_name": app_name} if app_name else {},
            payload=payload,
        )
        self.with_context(skip_gateway_push=True)._upsert_items([response])

    def _get_app_name(self):
        self.ensure_one()
        bank_account = self.env["pf.gateway.bank.account"].search(
            [
                "|",
                ("external_id", "=", self.bank_account_external_id),
                ("cvu_cbu", "=", self.cvu_cbu),
            ],
            limit=1,
        )
        return (bank_account.app or "").strip() if bank_account else ""

    def _prepare_values(self, item):
        if not isinstance(item, dict):
            raise UserError(_("La respuesta del gateway contiene items inválidos."))

        return {
            "external_id": str(item.get("id")),
            "active": True,
            "bank_account_external_id": item.get("bank_account_id") or False,
            "cvu_cbu": item.get("cvu_cbu") or False,
            "commission_percentage": float(item.get("commission_percentage") or 0.0),
            "is_active": bool(item.get("is_active")),
            "created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _upsert_items(self, items):
        if not items:
            return 0

        prepared = [self._prepare_values(item) for item in items]
        external_ids = [values["external_id"] for values in prepared if values.get("external_id")]
        existing = self.search([("external_id", "in", external_ids)]) if external_ids else self.browse()
        existing_map = {record.external_id: record for record in existing}

        for values in prepared:
            record = existing_map.get(values["external_id"])
            if record:
                record.write(values)
            else:
                self.create(values)

        return len(prepared)

    @api.model
    def sync_from_gateway(self, cvu_cbu=None, limit=200, offset=0):
        path = "/admin/gateway/incoming-transfer-commission/accounts"
        page_limit = max(1, int(limit or 200))
        current_offset = max(0, int(offset or 0))
        processed = 0

        while True:
            params = {
                "limit": page_limit,
                "offset": current_offset,
            }
            if cvu_cbu:
                params["cvu_cbu"] = cvu_cbu

            payload = self._gateway_request_json("GET", path, params=params)
            items = payload.get("items") or []
            if not isinstance(items, list):
                raise UserError(_("La respuesta del gateway no contiene una lista válida en 'items'."))

            processed += self._upsert_items(items)
            total = int(payload.get("total") or 0)

            if not items:
                break
            if current_offset + len(items) >= total:
                break
            if len(items) < page_limit:
                break

            current_offset += page_limit

        return processed

    def action_sync_all_from_gateway(self):
        processed = self.env["pf.gateway.incoming.transfer.commission.account"].sync_from_gateway()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisiones por usuario sincronizadas"),
                "message": _("Se procesaron %s registros.") % processed,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_sync_this_cvu(self):
        self.ensure_one()
        if not self.cvu_cbu:
            raise UserError(_("Este registro no tiene CVU/CBU para sincronizar."))

        processed = self.env["pf.gateway.incoming.transfer.commission.account"].sync_from_gateway(cvu_cbu=self.cvu_cbu)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisión por CVU sincronizada"),
                "message": _("Se procesaron %s registros para %s.") % (processed, self.cvu_cbu),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_open_sync_wizard(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "pf.gateway.incoming.transfer.commission.account.sync.wizard",
            "view_mode": "form",
            "target": "new",
        }