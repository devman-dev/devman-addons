import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayCompanyLocation(models.Model):
    _name = "pf.gateway.company.location"
    _description = "Local de empresa en PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(string="Nombre", required=True)
    external_id = fields.Char(string="ID gateway", index=True, readonly=True)
    company_id = fields.Many2one(
        "pf.gateway.company",
        string="Empresa",
        required=True,
        ondelete="cascade",
        index=True,
    )
    branch_code = fields.Char(string="Código de sucursal", required=True)
    bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria",
        ondelete="restrict",
        index=True,
    )
    contact_name = fields.Char(string="Contacto")
    contact_email = fields.Char(string="Email contacto")
    contact_phone = fields.Char(string="Teléfono contacto")
    is_active = fields.Boolean(string="Activo", default=True)
    location_commission_agent_ids = fields.One2many(
        "pf.gateway.company.location.commission.agent",
        "location_id",
        string="Comisionistas",
    )
    source_created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    source_updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_company_location_external_id_uniq",
            "unique(external_id)",
            "El ID gateway del local debe ser único.",
        ),
        (
            "pf_gateway_company_location_bank_account_uniq",
            "unique(bank_account_id)",
            "Ya existe un local con esta cuenta bancaria.",
        ),
        (
            "pf_gateway_company_location_company_branch_code_uniq",
            "unique(company_id, branch_code)",
            "Ya existe un local con este código de sucursal para la empresa.",
        ),
    ]

    def _gateway_payload(self):
        self.ensure_one()
        if not self.company_id.external_id:
            raise UserError(_("La empresa seleccionada no tiene ID gateway."))

        # Permite guardar el local sin cuenta y completar luego desde el wizard.
        if not self.bank_account_id:
            return {}
        if not self.bank_account_id.external_id:
            raise UserError(_("La cuenta bancaria seleccionada no tiene ID gateway."))
        return {
            "company_id": self.company_id.external_id,
            "name": self.name,
            "branch_code": self.branch_code,
            "bank_account_id": self.bank_account_id.external_id,
            "contact_name": self.contact_name or None,
            "contact_email": self.contact_email or None,
            "contact_phone": self.contact_phone or None,
            "is_active": bool(self.is_active),
        }

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return
        vals = self._values_from_gateway_item(payload)
        vals["raw_payload"] = self._payload_to_text(payload)
        self.with_context(skip_gateway_company_location_push=True).write(vals)

    def _values_from_gateway_item(self, item):
        company_external_id = item.get("company_id")
        bank_account_external_id = item.get("bank_account_id")
        if not company_external_id:
            raise UserError(_("El gateway no devolvió company_id para un local de empresa."))
        if not bank_account_external_id:
            raise UserError(_("El gateway no devolvió bank_account_id para un local de empresa."))

        company = self.env["pf.gateway.company"].search(
            [("external_id", "=", str(company_external_id))], limit=1
        )
        if not company:
            raise UserError(
                _("No existe la empresa local para company_id=%s. Sincroniza empresas primero.") % company_external_id
            )
        bank_account = self.env["pf.gateway.bank.account"].search(
            [("external_id", "=", str(bank_account_external_id))], limit=1
        )
        if not bank_account:
            raise UserError(
                _("No existe la cuenta bancaria local para bank_account_id=%s. Sincroniza cuentas primero.") % bank_account_external_id
            )

        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "company_id": company.id,
            "name": item.get("name"),
            "branch_code": item.get("branch_code"),
            "bank_account_id": bank_account.id,
            "contact_name": item.get("contact_name"),
            "contact_email": item.get("contact_email"),
            "contact_phone": item.get("contact_phone"),
            "is_active": item.get("is_active", True),
            "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_company_location_push"):
            return records

        for record in records:
            if not record.bank_account_id:
                continue
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/company-locations",
                payload=record._gateway_payload(),
            )
            record._update_from_gateway_payload(response)
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_gateway_company_location_push"):
            return result

        push_fields = {
            "name",
            "branch_code",
            "bank_account_id",
            "contact_name",
            "contact_email",
            "contact_phone",
            "is_active",
        }
        if not push_fields.intersection(vals):
            return result

        for record in self:
            if not record.bank_account_id:
                continue
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/company-locations",
                payload=record._gateway_payload(),
            )
            record._update_from_gateway_payload(response)
        return result

    def unlink(self):
        if self.env.context.get("skip_gateway_company_location_push"):
            return super().unlink()

        for record in self:
            if not record.external_id:
                continue
            record._gateway_request_json(
                "DELETE",
                f"/admin/gateway/company-locations/{record.external_id}",
            )
        return super().unlink()

    def action_sync_company_locations(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def action_sync_location_commission_agents(self):
        self.ensure_one()
        _logger.info(
            "[CompanyLocation] action_sync_location_commission_agents location_id=%s external_id=%s",
            self.id,
            self.external_id,
        )
        self.env["pf.gateway.company.location.commission.agent"].sync_from_gateway(
            mode="manual",
            sync_mode="incremental",
            location=self,
        )
        return True

    def action_create_subaccount(self):
        self.ensure_one()
        _logger.info(
            "[CompanyLocation] action_create_subaccount location_id=%s external_id=%s",
            self.id,
            self.external_id,
        )
        company_user = self.company_id.created_by_user_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Crear cuenta bancaria para %s") % self.name,
            "res_model": "pf.gateway.company.location.create.subaccount.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_location_id": self.id,
                "default_user_id": company_user.id if company_user else False,
            },
        }

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", company=None, job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        extra_params = {}
        if company and company.external_id:
            extra_params["company_id"] = company.external_id

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar locales de empresa ({sync_mode})",
                "resource": "company-locations",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            _logger.info(
                "[CompanyLocation] SYNC pull -> GET /admin/gateway/company-locations "
                "updated_since=%s extra_params=%s",
                updated_since,
                extra_params,
            )
            items = self._gateway_paginated_get(
                "/admin/gateway/company-locations",
                updated_since=updated_since,
                extra_params=extra_params,
            )
            _logger.info("[CompanyLocation] SYNC pull <- %s items", len(items))
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
                    record.with_context(skip_gateway_company_location_push=True).write(values)
                else:
                    self.with_context(skip_gateway_company_location_push=True).create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Locales de empresa sincronizados: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de locales de empresa falló.",
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
