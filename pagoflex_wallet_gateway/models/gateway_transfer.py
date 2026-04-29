from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewayTransfer(models.Model):
    _name = "pf.gateway.transfer"
    _description = "Transferencia de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "transaction_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    payment_id = fields.Char(index=True)
    origin_id = fields.Char(index=True)
    status = fields.Char(index=True)
    movement_nature = fields.Selection(
        [
            ("TRANSFER", "Transferencia"),
            ("COMMISSION", "Comisión"),
        ],
        index=True,
    )
    amount = fields.Float(digits=(16, 2))
    currency = fields.Char()
    concept = fields.Char()
    description = fields.Text()
    connector_id = fields.Char(index=True, string="ID Coelsa")
    source_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta origen", ondelete="set null", index=True)
    destination_bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta destino", ondelete="set null", index=True)
    source_user_id = fields.Many2one("pf.gateway.user", string="Usuario origen", ondelete="set null", index=True)
    destination_user_id = fields.Many2one("pf.gateway.user", string="Usuario destino", ondelete="set null", index=True)
    source_address = fields.Char()
    source_address_type = fields.Char()
    source_owner_id_type = fields.Char()
    source_owner_id = fields.Char()
    source_owner_name = fields.Char()
    destination_address = fields.Char()
    destination_address_type = fields.Char()
    destination_owner_id_type = fields.Char()
    destination_owner_id = fields.Char()
    destination_owner_name = fields.Char()
    extra_metadata = fields.Text()
    connector_response = fields.Text()
    source_created_at = fields.Datetime()
    source_updated_at = fields.Datetime(index=True)
    transaction_at = fields.Datetime(index=True)
    last_sync_at = fields.Datetime(index=True)
    raw_payload = fields.Text()

    _sql_constraints = [
        ("pf_gateway_transfer_external_id_uniq", "unique(external_id)", "El external_id de la transferencia del gateway debe ser único."),
    ]

    @api.depends("origin_id", "payment_id", "movement_nature")
    def _compute_name(self):
        for record in self:
            label = record.origin_id or record.payment_id or record.external_id
            if record.movement_nature:
                record.name = f"[{record.movement_nature}] {label}"
            else:
                record.name = label

    def action_sync_transfers(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def action_sync_transfers_full(self):
        self.sync_from_gateway(mode="manual", sync_mode="full")
        return True

    def action_query_by_origin_id(self):
        self.ensure_one()
        if not self.origin_id:
            raise UserError(_("Esta transferencia no tiene Origin ID asignado."))
        response = self._gateway_request_json(
            "GET", f"/admin/gateway/bdc/direct/transfers/by-origin-id/{self.origin_id}"
        )
        return self._open_response_wizard(_("Consulta por Origin ID"), response)

    def action_query_by_connector_id(self):
        self.ensure_one()
        if not self.connector_id:
            raise UserError(_("Esta transferencia no tiene Connector ID asignado."))
        response = self._gateway_request_json(
            "GET", f"/admin/gateway/bdc/direct/transfers/by-id-coelsa/{self.connector_id}"
        )
        return self._open_response_wizard(_("Consulta por Connector ID (Coelsa)"), response)

    def _open_response_wizard(self, title, response):
        response_text = self._payload_to_text(response)
        self.sudo().write({"connector_response": response_text})
        wizard = self.env["pf.gateway.transfer.response.wizard"].create({
            "title": title,
            "response_text": response_text,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": "pf.gateway.transfer.response.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
            "name": title,
        }

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        transfer_model = self.sudo()
        updated_since = None
        if sync_mode == "incremental":
            updated_since = transfer_model.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar transferencias ({sync_mode})",
                "resource": "transfers",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get("/admin/gateway/transfers", updated_since=updated_since)
            account_model = self.env["pf.gateway.bank.account"]
            user_model = self.env["pf.gateway.user"]
            for item in items:
                source_account = account_model.search([("external_id", "=", item.get("source_account_id"))], limit=1)
                destination_account = account_model.search([("external_id", "=", item.get("destination_account_id"))], limit=1)
                source_user = source_account.gateway_user_id if source_account else user_model.browse()
                destination_user = destination_account.gateway_user_id if destination_account else user_model.browse()
                values = {
                    "external_id": str(item.get("id")),
                    "active": True,
                    "payment_id": item.get("payment_id"),
                    "origin_id": item.get("origin_id"),
                    "status": item.get("status"),
                    "movement_nature": item.get("movement_nature"),
                    "amount": item.get("amount") or 0.0,
                    "currency": item.get("currency"),
                    "concept": item.get("concept"),
                    "description": item.get("description"),
                    "connector_id": item.get("connector_id"),
                    "source_bank_account_id": source_account.id,
                    "destination_bank_account_id": destination_account.id,
                    "source_user_id": source_user.id,
                    "destination_user_id": destination_user.id,
                    "source_address": item.get("source_address"),
                    "source_address_type": item.get("source_address_type"),
                    "source_owner_id_type": item.get("source_owner_id_type"),
                    "source_owner_id": item.get("source_owner_id"),
                    "source_owner_name": item.get("source_owner_name"),
                    "destination_address": item.get("destination_address"),
                    "destination_address_type": item.get("destination_address_type"),
                    "destination_owner_id_type": item.get("destination_owner_id_type"),
                    "destination_owner_id": item.get("destination_owner_id"),
                    "destination_owner_name": item.get("destination_owner_name"),
                    "extra_metadata": self._payload_to_text(item.get("extra_metadata")),
                    "connector_response": self._payload_to_text(item.get("connector_response")),
                    "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
                    "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
                    "transaction_at": self._coerce_datetime(item.get("transaction_at"), field_name="transaction_at"),
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self._payload_to_text(item),
                }
                record = transfer_model.search([("external_id", "=", values["external_id"])], limit=1)
                if record:
                    record.write(values)
                else:
                    transfer_model.create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Transferencias sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de transferencias fallo.",
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

