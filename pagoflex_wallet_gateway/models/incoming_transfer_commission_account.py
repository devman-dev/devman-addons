from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewayIncomingTransferCommissionAccount(models.Model):
    _name = "pf.gateway.incoming.transfer.commission.account"
    _description = "Comisión de transferencias entrantes por cuenta"
    _inherit = "pf.gateway.client.mixin"
    _order = "updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    bank_account_external_id = fields.Char(string="ID cuenta bancaria", index=True)
    cvu_cbu = fields.Char(string="CVU/CBU", index=True)
    commission_percentage = fields.Float(string="Porcentaje de comisión", digits=(16, 4))
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