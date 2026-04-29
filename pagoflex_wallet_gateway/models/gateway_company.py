from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PfGatewayCompany(models.Model):
    _name = "pf.gateway.company"
    _description = "Cuenta empresa de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(string="Razón social", required=True)
    active = fields.Boolean(string="Activo", default=True)
    external_id = fields.Char(string="ID gateway", index=True, readonly=True)
    partner_id = fields.Many2one("res.partner", string="Contacto Odoo", ondelete="restrict", index=True)
    cuit = fields.Char(required=True, index=True)
    contact_name = fields.Char(string="Contacto")
    contact_email = fields.Char(string="Email contacto")
    contact_phone = fields.Char(string="Teléfono contacto")
    created_by_user_id = fields.Many2one("pf.gateway.user", string="Creado por", ondelete="set null", index=True)
    primary_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria principal",
        ondelete="set null",
        index=True,
    )
    child_gateway_user_ids = fields.One2many(
        "pf.gateway.user",
        "parent_company_gateway_user_id",
        string="Usuarios finales vinculados",
    )
    company_membership_ids = fields.One2many(
        "pf.gateway.company.membership",
        "company_id",
        string="Membresias",
    )
    source_created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    source_updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        ("pf_gateway_company_external_id_uniq", "unique(external_id)", "El ID gateway de la cuenta empresa debe ser único."),
        ("pf_gateway_company_cuit_uniq", "unique(cuit)", "El CUIT de la cuenta empresa debe ser único."),
    ]

    def _gateway_company_payload(self):
        self.ensure_one()
        return {
            "name": self.name,
            "cuit": self.cuit,
            "contact_name": self.contact_name or None,
            "contact_email": self.contact_email or None,
            "contact_phone": self.contact_phone or None,
            "created_by_user_id": self.created_by_user_id.external_id or None if self.created_by_user_id else None,
            "primary_bank_account_id": self.primary_bank_account_id.external_id or None if self.primary_bank_account_id else None,
            "is_active": bool(self.active),
        }

    def _partner_search_domain_from_company_values(self, values):
        cuit = values.get("cuit")
        email = values.get("contact_email")
        if cuit:
            return [("vat", "=", cuit)]
        if email:
            return [("email", "=", email)]
        return []

    def _partner_values_from_company_values(self, values):
        return {
            "name": values.get("name") or values.get("contact_name") or values.get("contact_email") or values.get("cuit"),
            "company_type": "company",
            "is_company": True,
            "vat": values.get("cuit") or False,
            "email": values.get("contact_email") or False,
            "phone": values.get("contact_phone") or False,
        }

    def _find_or_create_partner_from_company_values(self, values):
        domain = self._partner_search_domain_from_company_values(values)
        partner = self.env["res.partner"].search(domain, limit=1) if domain else self.env["res.partner"]
        partner_values = self._partner_values_from_company_values(values)
        if partner:
            update_values = {
                key: value
                for key, value in partner_values.items()
                if value and (key in {"company_type", "is_company"} or not partner[key])
            }
            if update_values:
                partner.write(update_values)
            return partner
        return self.env["res.partner"].create(partner_values)

    def _ensure_partner_link(self):
        for record in self:
            if record.partner_id:
                continue
            partner = record._find_or_create_partner_from_company_values(
                {
                    "name": record.name,
                    "cuit": record.cuit,
                    "contact_name": record.contact_name,
                    "contact_email": record.contact_email,
                    "contact_phone": record.contact_phone,
                }
            )
            record.with_context(skip_gateway_company_push=True).partner_id = partner.id

    def _update_from_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            return

        vals = self._values_from_gateway_item(payload)
        vals["raw_payload"] = self._payload_to_text(payload)
        self.with_context(skip_gateway_company_push=True).write(vals)

    def _gateway_company_patch_path(self):
        self.ensure_one()
        if not self.external_id:
            raise UserError(_("La cuenta empresa no tiene ID gateway para actualizar."))
        return f"/admin/gateway/companies/{self.external_id}"

    def _values_from_gateway_item(self, item):
        company_values = {
            "name": item.get("name") or item.get("business_name") or item.get("company_name"),
            "cuit": item.get("cuit") or item.get("cuit_cuil"),
            "contact_name": item.get("contact_name"),
            "contact_email": item.get("contact_email"),
            "contact_phone": item.get("contact_phone"),
        }
        partner = self._find_or_create_partner_from_company_values(company_values)

        created_by = self.env["pf.gateway.user"]
        created_by_external_id = item.get("created_by_user_id")
        if created_by_external_id:
            created_by = created_by.search([("external_id", "=", str(created_by_external_id))], limit=1)

        primary_bank_account = self.env["pf.gateway.bank.account"]
        primary_bank_account_external_id = item.get("primary_bank_account_id")
        if primary_bank_account_external_id:
            primary_bank_account = primary_bank_account.search(
                [("external_id", "=", str(primary_bank_account_external_id))],
                limit=1,
            )

        return {
            "external_id": str(item.get("id")) if item.get("id") is not None else False,
            "partner_id": partner.id,
            "name": company_values["name"],
            "cuit": company_values["cuit"],
            "contact_name": company_values["contact_name"],
            "contact_email": company_values["contact_email"],
            "contact_phone": company_values["contact_phone"],
            "created_by_user_id": created_by.id,
            "primary_bank_account_id": primary_bank_account.id,
            "active": item.get("is_active", True),
            "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("skip_gateway_company_push"):
            for vals in vals_list:
                if not vals.get("partner_id"):
                    partner = self._find_or_create_partner_from_company_values(vals)
                    vals["partner_id"] = partner.id
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_company_push"):
            return records

        for record in records:
            response = record._gateway_request_json(
                "POST",
                "/admin/gateway/companies",
                payload=record._gateway_company_payload(),
            )
            record._update_from_gateway_payload(response)
        return records

    def write(self, vals):
        result = super().write(vals)
        if self.env.context.get("skip_gateway_company_push"):
            return result

        if {"name", "cuit", "contact_name", "contact_email", "contact_phone"}.intersection(vals):
            self._ensure_partner_link()

        push_fields = {
            "name",
            "cuit",
            "contact_name",
            "contact_email",
            "contact_phone",
            "created_by_user_id",
            "primary_bank_account_id",
            "active",
        }
        if not push_fields.intersection(vals):
            return result

        for record in self:
            method = "PATCH" if record.external_id else "POST"
            path = record._gateway_company_patch_path() if record.external_id else "/admin/gateway/companies"
            response = record._gateway_request_json(
                method,
                path,
                payload=record._gateway_company_payload(),
            )
            record._update_from_gateway_payload(response)
        return result

    def action_sync_companies(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar cuentas empresas ({sync_mode})",
                "resource": "companies",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get("/admin/gateway/companies", updated_since=updated_since)
            for item in items:
                values = self._values_from_gateway_item(item)
                record = self.search([("external_id", "=", values["external_id"])], limit=1)
                if not record and values.get("cuit"):
                    record = self.search([("cuit", "=", values["cuit"])], limit=1)
                if record:
                    record.with_context(skip_gateway_company_push=True).write(values)
                    company_record = record
                else:
                    company_record = self.with_context(skip_gateway_company_push=True).create(values)
                memberships = self.env["pf.gateway.company.membership"].search(
                    ["|", ("company_external_id", "=", company_record.external_id), ("company_cuit", "=", company_record.cuit)]
                )
                memberships.write({"company_id": company_record.id})
                memberships._refresh_user_company_shortcut()

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Cuentas empresas sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de cuentas empresas fallo.",
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
