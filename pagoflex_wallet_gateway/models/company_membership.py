from odoo import _, api, fields, models


class PfGatewayCompanyMembership(models.Model):
    _name = "pf.gateway.company.membership"
    _description = "Membresia de empresa PagoFlex"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    external_id = fields.Char(string="ID gateway", required=True, index=True)
    company_id = fields.Many2one("pf.gateway.company", string="Empresa", ondelete="set null", index=True)
    company_external_id = fields.Char(string="ID empresa gateway", index=True)
    company_name = fields.Char(string="Empresa")
    company_cuit = fields.Char(string="CUIT empresa", index=True)
    user_id = fields.Many2one("pf.gateway.user", string="Usuario", ondelete="set null", index=True)
    user_external_id = fields.Char(string="ID usuario gateway", index=True)
    user_email = fields.Char(string="Email usuario", index=True)
    user_partner_id = fields.Many2one(related="user_id.partner_id", string="Contacto usuario", store=True)
    bank_account_id = fields.Many2one("pf.gateway.bank.account", string="Cuenta bancaria", ondelete="set null", index=True)
    bank_account_external_id = fields.Char(string="ID cuenta bancaria gateway", index=True)
    bank_account_cvu_cbu = fields.Char(string="CVU/CBU", index=True)
    role = fields.Char(index=True)
    active = fields.Boolean(default=True, index=True)
    source_created_at = fields.Datetime(string="Creado en gateway", readonly=True)
    source_updated_at = fields.Datetime(string="Actualizado en gateway", readonly=True, index=True)
    last_sync_at = fields.Datetime(string="Ultima sincronizacion", readonly=True, index=True)
    raw_payload = fields.Text(string="Payload crudo", readonly=True)

    _sql_constraints = [
        (
            "pf_gateway_company_membership_external_id_uniq",
            "unique(external_id)",
            "El ID gateway de la membresia debe ser unico.",
        ),
    ]

    @api.depends("company_name", "user_email", "role", "external_id")
    def _compute_name(self):
        for record in self:
            parts = [part for part in (record.company_name, record.user_email, record.role) if part]
            record.name = " / ".join(parts) or record.external_id

    def _normalise_cuit(self, value):
        return "".join(char for char in str(value or "") if char.isdigit())

    def _resolve_company(self, item):
        company = self.env["pf.gateway.company"]
        company_external_id = item.get("company_id")
        company_cuit = item.get("company_cuit") or item.get("owner_cuit")
        if company_external_id:
            company = company.search([("external_id", "=", str(company_external_id))], limit=1)
        if not company and company_cuit:
            normalised = self._normalise_cuit(company_cuit)
            for candidate in company.search([("cuit", "!=", False)]):
                if self._normalise_cuit(candidate.cuit) == normalised:
                    return candidate
        return company

    def _resolve_user(self, item):
        user_external_id = item.get("user_id")
        if not user_external_id:
            return self.env["pf.gateway.user"]
        return self.env["pf.gateway.user"].search([("external_id", "=", str(user_external_id))], limit=1)

    def _resolve_bank_account(self, item):
        bank_account_external_id = item.get("bank_account_id")
        bank_account = self.env["pf.gateway.bank.account"]
        if bank_account_external_id:
            bank_account = bank_account.search([("external_id", "=", str(bank_account_external_id))], limit=1)
        if not bank_account and item.get("bank_account_cvu_cbu"):
            bank_account = bank_account.search([("cvu_cbu", "=", item.get("bank_account_cvu_cbu"))], limit=1)
        return bank_account

    def _values_from_gateway_item(self, item):
        company = self._resolve_company(item)
        user = self._resolve_user(item)
        bank_account = self._resolve_bank_account(item)
        return {
            "external_id": str(item.get("id")),
            "company_id": company.id,
            "company_external_id": str(item.get("company_id")) if item.get("company_id") else False,
            "company_name": item.get("company_name"),
            "company_cuit": item.get("company_cuit") or item.get("owner_cuit"),
            "user_id": user.id,
            "user_external_id": str(item.get("user_id")) if item.get("user_id") else False,
            "user_email": item.get("user_email"),
            "bank_account_id": bank_account.id,
            "bank_account_external_id": str(item.get("bank_account_id")) if item.get("bank_account_id") else False,
            "bank_account_cvu_cbu": item.get("bank_account_cvu_cbu"),
            "role": item.get("role"),
            "active": item.get("is_active", True),
            "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _upsert_gateway_item(self, item):
        values = self._values_from_gateway_item(item)
        record = self.search([("external_id", "=", values["external_id"])], limit=1)
        if record:
            record.write(values)
        else:
            record = self.create(values)
        record._apply_current_backend_uniqueness()
        record._refresh_user_company_shortcut()
        return record

    def _apply_current_backend_uniqueness(self):
        for record in self.filtered("active"):
            domain = [("id", "!=", record.id), ("active", "=", True)]
            duplicate_domain = []
            if record.user_external_id:
                duplicate_domain.append(("user_external_id", "=", record.user_external_id))
            if record.bank_account_external_id:
                duplicate_domain.append(("bank_account_external_id", "=", record.bank_account_external_id))
            if not duplicate_domain:
                continue
            if len(duplicate_domain) == 1:
                domain.append(duplicate_domain[0])
            else:
                domain.extend(["|"] + duplicate_domain)
            duplicates = self.search(domain)
            if duplicates:
                duplicates.write({"active": False})
                duplicates._refresh_user_company_shortcut()

    def _refresh_user_company_shortcut(self):
        for user in self.mapped("user_id"):
            active_membership = self.search(
                [("user_id", "=", user.id), ("active", "=", True), ("company_id", "!=", False)],
                order="source_updated_at desc, id desc",
                limit=1,
            )
            user.write(
                {
                    "parent_company_gateway_user_id": active_membership.company_id.id,
                    "cuit_owner": active_membership.company_cuit or active_membership.company_id.cuit,
                }
            )

    def _sync_params(self, *, owner_cuit=None, is_active=None):
        if owner_cuit is None:
            owner_cuit = self._gateway_param("pagoflex_wallet_gateway.membership_owner_cuit", "")
        if is_active is None:
            raw_active = (self._gateway_param("pagoflex_wallet_gateway.membership_is_active", "") or "").strip().lower()
            if raw_active in {"1", "true", "yes"}:
                is_active = True
            elif raw_active in {"0", "false", "no"}:
                is_active = False
        params = {}
        if owner_cuit:
            params["owner_cuit"] = owner_cuit
        if is_active is not None:
            params["is_active"] = bool(is_active)
        return params

    def action_sync_memberships(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None, owner_cuit=None, is_active=None):
        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar membresias de empresas ({sync_mode})",
                "resource": "company_memberships",
                "mode": mode,
                "job_id": job.id if job else False,
            }
        )
        try:
            items = self._gateway_paginated_get(
                "/admin/gateway/company-memberships",
                extra_params=self._sync_params(owner_cuit=owner_cuit, is_active=is_active),
            )
            for item in items:
                self._upsert_gateway_item(item)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Membresias de empresas sincronizadas: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronizacion de membresias de empresas fallo.",
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
