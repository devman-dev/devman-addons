import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayCompanyLocationCommissionAgent(models.Model):
    _name = "pf.gateway.company.location.commission.agent"
    _description = "Comisionista de local de empresa en PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    external_id = fields.Char(string="ID gateway", readonly=True, index=True)
    location_id = fields.Many2one(
        "pf.gateway.company.location",
        string="Local",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        "pf.gateway.company",
        string="Empresa",
        related="location_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )
    user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario",
        ondelete="set null",
        index=True,
    )
    bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria",
        required=True,
        ondelete="restrict",
        index=True,
    )
    commission_percentage = fields.Float(
        string="Porcentaje de comisión",
        required=True,
        digits=(16, 4),
        default=0.0,
    )
    is_active = fields.Boolean(string="Activo", default=True)
    source_created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    source_updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_company_location_commission_agent_external_id_uniq",
            "unique(external_id)",
            "El ID gateway del comisionista de local debe ser único.",
        ),
        (
            "pf_gateway_company_location_commission_agent_location_bank_uniq",
            "unique(location_id, bank_account_id)",
            "Ya existe un comisionista con esta cuenta bancaria para el local.",
        ),
        (
            "pf_gateway_company_location_commission_agent_pct_nonneg",
            "check(commission_percentage >= 0)",
            "El porcentaje de comisión no puede ser negativo.",
        ),
    ]

    @api.depends("external_id", "location_id", "bank_account_id")
    def _compute_name(self):
        for record in self:
            parts = [
                record.location_id.name,
                record.bank_account_id.cvu_cbu,
                record.external_id,
            ]
            record.name = " - ".join([p for p in parts if p]) or _("Comisionista de local gateway")

    def _gateway_payload(self):
        self.ensure_one()
        if not self.location_id.external_id:
            raise UserError(_("El local seleccionado no tiene ID gateway."))
        if not self.bank_account_id.external_id:
            raise UserError(_("La cuenta bancaria seleccionada no tiene ID gateway."))
        if self.user_id and not self.user_id.external_id:
            raise UserError(_("El usuario seleccionado no tiene ID gateway."))

        payload = {
            "location_id": self.location_id.external_id,
            "user_id": self.user_id.external_id if self.user_id else None,
            "bank_account_id": self.bank_account_id.external_id,
            "commission_percentage": self.commission_percentage,
            "is_active": bool(self.is_active),
        }
        if self.external_id:
            payload["id"] = self.external_id
        return payload

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return
        vals = self._values_from_gateway_item(payload)
        vals["raw_payload"] = self._payload_to_text(payload)
        self.with_context(skip_gateway_company_location_commission_agent_push=True).write(vals)

    def _values_from_gateway_item(self, item):
        location_external_id = item.get("location_id")
        bank_account_external_id = item.get("bank_account_id")
        if not location_external_id:
            raise UserError(_("El gateway no devolvió location_id para un comisionista de local."))
        if not bank_account_external_id:
            raise UserError(_("El gateway no devolvió bank_account_id para un comisionista de local."))

        location = self.env["pf.gateway.company.location"].search(
            [("external_id", "=", str(location_external_id))], limit=1
        )
        if not location:
            raise UserError(
                _("No existe el local local para location_id=%s. Sincroniza locales primero.") % location_external_id
            )
        bank_account = self.env["pf.gateway.bank.account"].search(
            [("external_id", "=", str(bank_account_external_id))], limit=1
        )
        if not bank_account:
            raise UserError(
                _("No existe la cuenta bancaria local para bank_account_id=%s. Sincroniza cuentas primero.") % bank_account_external_id
            )

        user_external_id = item.get("user_id")
        user = self.env["pf.gateway.user"]
        if user_external_id:
            user = user.search([("external_id", "=", str(user_external_id))], limit=1)

        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "location_id": location.id,
            "user_id": user.id,
            "bank_account_id": bank_account.id,
            "commission_percentage": item.get("commission_percentage") or 0.0,
            "is_active": item.get("is_active", True),
            "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_company_location_commission_agent_push"):
            return records

        for record in records:
            payload = record._gateway_payload()
            _logger.info(
                "[LocationCommissionAgent] PUSH create -> POST /admin/gateway/company-location-commission-agents payload=%s",
                payload,
            )
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/company-location-commission-agents",
                payload=payload,
            )
            record._update_from_gateway_payload(response)
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_gateway_company_location_commission_agent_push"):
            return result

        push_fields = {"location_id", "user_id", "bank_account_id", "commission_percentage", "is_active"}
        if not push_fields.intersection(vals):
            return result

        for record in self:
            payload = record._gateway_payload()
            _logger.info(
                "[LocationCommissionAgent] PUSH write -> POST /admin/gateway/company-location-commission-agents "
                "external_id=%s payload=%s",
                record.external_id,
                payload,
            )
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/company-location-commission-agents",
                payload=payload,
            )
            record._update_from_gateway_payload(response)
        return result

    def unlink(self):
        if self.env.context.get("skip_gateway_company_location_commission_agent_push"):
            return super().unlink()

        for record in self:
            if not record.external_id:
                continue
            record._gateway_request_json(
                "DELETE",
                f"/admin/gateway/company-location-commission-agents/{record.external_id}",
            )
        return super().unlink()

    def action_sync_location_commission_agents(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", location=None, company=None, job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        extra_params = {}
        if location and location.external_id:
            extra_params["location_id"] = location.external_id
        elif company and company.external_id:
            extra_params["company_id"] = company.external_id

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar comisionistas de locales ({sync_mode})",
                "resource": "company-location-commission-agents",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            _logger.info(
                "[LocationCommissionAgent] SYNC pull -> GET /admin/gateway/company-location-commission-agents "
                "updated_since=%s extra_params=%s",
                updated_since,
                extra_params,
            )
            items = self._gateway_paginated_get(
                "/admin/gateway/company-location-commission-agents",
                updated_since=updated_since,
                extra_params=extra_params,
            )
            _logger.info("[LocationCommissionAgent] SYNC pull <- %s items", len(items))
            for item in items:
                values = self._values_from_gateway_item(item)
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if not record:
                    record = self.search(
                        [
                            ("location_id", "=", values["location_id"]),
                            ("bank_account_id", "=", values["bank_account_id"]),
                        ],
                        limit=1,
                    )
                if record:
                    record.with_context(skip_gateway_company_location_commission_agent_push=True).write(values)
                else:
                    self.with_context(skip_gateway_company_location_commission_agent_push=True).create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Comisionistas de locales sincronizados: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de comisionistas de locales falló.",
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
