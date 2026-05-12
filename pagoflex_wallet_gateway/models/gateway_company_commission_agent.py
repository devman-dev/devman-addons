import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError


class PfGatewayCompanyCommissionAgent(models.Model):
    _name = "pf.gateway.company.commission.gateway.agent"
    _description = "Comisionista de empresa en PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    external_id = fields.Char(string="ID gateway", readonly=True, index=True)
    company_id = fields.Many2one("pf.gateway.company", string="Empresa", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("pf.gateway.user", string="Usuario", ondelete="set null", index=True)
    company_app_name = fields.Char(
        string="App empresa",
        related="company_id.primary_bank_account_id.app",
        store=True,
        readonly=True,
    )
    bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('gateway_user_id', '=', user_id), ('app', '=', company_app_name)]",
    )
    commission_percentage = fields.Float(string="Porcentaje de comisión", required=True, digits=(16, 4), default=0.0)
    is_active = fields.Boolean(string="Activo", default=True)
    source_created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    source_updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_company_commission_gateway_agent_external_id_uniq",
            "unique(external_id)",
            "El ID gateway del comisionista de empresa debe ser único.",
        ),
        (
            "pf_gateway_company_commission_gateway_agent_company_bank_uniq",
            "unique(company_id, bank_account_id)",
            "Ya existe un comisionista para la combinación empresa/cuenta bancaria.",
        ),
    ]

    @api.onchange("user_id", "company_id")
    def _onchange_user_or_company(self):
        for record in self:
            _logger.debug(
                "[CommissionAgent] onchange user_id=%s company_id=%s "
                "company_app_name=%r primary_bank_account=%s",
                record.user_id.id if record.user_id else None,
                record.company_id.id if record.company_id else None,
                record.company_app_name,
                record.company_id.primary_bank_account_id.id if record.company_id else None,
            )
            # Si cambia el usuario, limpiar la cuenta bancaria previa para forzar reselección
            if record.user_id and record.bank_account_id:
                if record.bank_account_id.gateway_user_id != record.user_id:
                    _logger.debug(
                        "[CommissionAgent] Limpiando bank_account_id=%s porque no pertenece al nuevo user_id=%s",
                        record.bank_account_id.id,
                        record.user_id.id,
                    )
                    record.bank_account_id = False

    @api.depends("external_id", "company_id", "bank_account_id")
    def _compute_name(self):
        for record in self:
            parts = [record.company_id.name, record.bank_account_id.cvu_cbu, record.external_id]
            record.name = " - ".join([part for part in parts if part]) or _("Comisionista gateway")

    def _gateway_payload(self):
        self.ensure_one()
        if not self.company_id.external_id:
            raise UserError(_("La empresa seleccionada no tiene ID gateway."))
        if not self.bank_account_id.external_id:
            raise UserError(_("La cuenta bancaria seleccionada no tiene ID gateway."))
        if self.user_id and not self.user_id.external_id:
            raise UserError(_("El usuario seleccionado no tiene ID gateway."))

        payload = {
            "company_id": self.company_id.external_id,
            "user_id": self.user_id.external_id or None if self.user_id else None,
            "bank_account_id": self.bank_account_id.external_id,
            "commission_percentage": self.commission_percentage,
            "is_active": bool(self.is_active),
        }
        if self.external_id:
            payload["id"] = self.external_id
        return payload

    def _is_company_not_found_gateway_error(self, exc):
        message = str(exc or "").lower()
        return "company_id no existe" in message

    def _ensure_company_exists_in_gateway(self):
        self.ensure_one()
        company = self.company_id

        method = "PATCH" if company.external_id else "POST"
        path = company._gateway_company_patch_path() if company.external_id else "/admin/gateway/companies"
        payload = company._gateway_company_payload()

        try:
            response = company._gateway_request_json(method, path, payload=payload)
        except UserError:
            if method != "PATCH":
                raise
            # Si el external_id local ya no existe en gateway, recrear por POST.
            response = company._gateway_request_json("POST", "/admin/gateway/companies", payload=payload)

        company._update_from_gateway_payload(response)
        return company

    def _post_company_commission_agent_with_company_retry(self, payload, *, log_context="write"):
        self.ensure_one()
        endpoint = "/admin/gateway/company-commission-agents"
        try:
            return self._gateway_request_json("POST", endpoint, payload=payload)
        except UserError as exc:
            if not self._is_company_not_found_gateway_error(exc):
                raise
            if not self.company_id.external_id:
                raise

            _logger.warning(
                "[CommissionAgent] company_id no existe en gateway. "
                "Se hace upsert de empresa y se reintenta una vez. "
                "context=%s company_external_id=%s",
                log_context,
                self.company_id.external_id,
            )
            refreshed_company = self._ensure_company_exists_in_gateway()
            if not refreshed_company.exists() or not refreshed_company.external_id:
                raise exc

            # Rearmar payload usando explicitamente el external_id actualizado.
            retry_payload = dict(payload)
            retry_payload["company_id"] = refreshed_company.external_id
            if self.external_id:
                retry_payload["id"] = self.external_id

            _logger.info(
                "[CommissionAgent] Reintento POST company-commission-agents context=%s "
                "company_external_id=%s payload=%s",
                log_context,
                refreshed_company.external_id,
                retry_payload,
            )
            return self._gateway_request_json("POST", endpoint, payload=retry_payload)

    def _resolve_required_company(self, external_id):
        company = self.env["pf.gateway.company"].search([("external_id", "=", str(external_id))], limit=1)
        if not company:
            raise UserError(_("No existe la empresa local para company_id=%s. Sincroniza empresas primero.") % external_id)
        return company

    def _resolve_required_bank_account(self, external_id):
        bank_account = self.env["pf.gateway.bank.account"].search([("external_id", "=", str(external_id))], limit=1)
        if not bank_account:
            raise UserError(
                _("No existe la cuenta bancaria local para bank_account_id=%s. Sincroniza cuentas primero.") % external_id
            )
        return bank_account

    def _resolve_optional_user(self, external_id):
        if not external_id:
            return self.env["pf.gateway.user"]
        return self.env["pf.gateway.user"].search([("external_id", "=", str(external_id))], limit=1)

    def _values_from_gateway_item(self, item):
        company_external_id = item.get("company_id")
        bank_account_external_id = item.get("bank_account_id")
        if not company_external_id:
            raise UserError(_("El gateway no devolvió company_id para un comisionista de empresa."))
        if not bank_account_external_id:
            raise UserError(_("El gateway no devolvió bank_account_id para un comisionista de empresa."))

        company = self._resolve_required_company(company_external_id)
        bank_account = self._resolve_required_bank_account(bank_account_external_id)
        user = self._resolve_optional_user(item.get("user_id"))

        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "company_id": company.id,
            "user_id": user.id,
            "bank_account_id": bank_account.id,
            "commission_percentage": item.get("commission_percentage") or 0.0,
            "is_active": item.get("is_active", True),
            "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return
        vals = self._values_from_gateway_item(payload)
        vals["raw_payload"] = self._payload_to_text(payload)
        self.with_context(skip_gateway_company_commission_agent_push=True).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_company_commission_agent_push"):
            return records

        for record in records:
            payload = record._gateway_payload()
            _logger.info(
                "[CommissionAgent] PUSH create -> POST /admin/gateway/company-commission-agents payload=%s",
                payload,
            )
            response = record._post_company_commission_agent_with_company_retry(payload, log_context="create")
            record._update_from_gateway_payload(response)
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_gateway_company_commission_agent_push"):
            return result

        push_fields = {"company_id", "user_id", "bank_account_id", "commission_percentage", "is_active"}
        if not push_fields.intersection(vals):
            return result

        for record in self:
            payload = record._gateway_payload()
            _logger.info(
                "[CommissionAgent] PUSH write -> POST /admin/gateway/company-commission-agents "
                "external_id=%s payload=%s",
                record.external_id,
                payload,
            )
            response = record._post_company_commission_agent_with_company_retry(payload, log_context="write")
            record._update_from_gateway_payload(response)
        return result

    def unlink(self):
        if self.env.context.get("skip_gateway_company_commission_agent_push"):
            return super().unlink()

        for record in self:
            if not record.external_id:
                continue
            record._gateway_request_json(
                "DELETE",
                f"/admin/gateway/company-commission-agents/{record.external_id}",
            )
        return super().unlink()

    def action_sync_company_commission_agents(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", company=None, job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        extra_params = {}
        if company and company.external_id:
            extra_params["company_id"] = company.external_id

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar comisionistas de empresa ({sync_mode})",
                "resource": "companies",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            _logger.info(
                "[CommissionAgent] SYNC pull -> GET /admin/gateway/company-commission-agents "
                "updated_since=%s extra_params=%s",
                updated_since,
                extra_params,
            )
            items = self._gateway_paginated_get(
                "/admin/gateway/company-commission-agents",
                updated_since=updated_since,
                extra_params=extra_params,
            )
            _logger.info("[CommissionAgent] SYNC pull <- %s items", len(items))
            for item in items:
                values = self._values_from_gateway_item(item)
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if not record:
                    record = self.search(
                        [
                            ("company_id", "=", values["company_id"]),
                            ("bank_account_id", "=", values["bank_account_id"]),
                        ],
                        limit=1,
                    )
                if record:
                    record.with_context(skip_gateway_company_commission_agent_push=True).write(values)
                else:
                    self.with_context(skip_gateway_company_commission_agent_push=True).create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Comisionistas de empresa sincronizados: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de comisionistas de empresa falló.",
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