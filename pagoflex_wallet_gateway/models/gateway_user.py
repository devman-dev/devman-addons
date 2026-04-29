from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PfGatewayUser(models.Model):
    _name = "pf.gateway.user"
    _description = "Usuario de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(required=True, index=True)
    email = fields.Char(index=True)
    full_name = fields.Char()
    first_name = fields.Char()
    last_name = fields.Char()
    birth_date = fields.Date()
    dni = fields.Char()
    gender = fields.Char()
    cuit_cuil = fields.Char()
    cuit_owner = fields.Char(string="CUIT empresa vinculada", index=True)
    phone = fields.Char()
    nationality = fields.Char()
    occupation = fields.Char()
    marital_status = fields.Char()
    location = fields.Char()
    is_email_verified = fields.Boolean()
    is_kyc_verified = fields.Boolean()
    source_created_at = fields.Datetime()
    source_updated_at = fields.Datetime(index=True)
    last_sync_at = fields.Datetime(index=True)
    raw_payload = fields.Text()
    partner_id = fields.Many2one("res.partner", string="Contacto Odoo", ondelete="restrict", index=True)
    partner_company_type = fields.Selection(related="partner_id.company_type", string="Tipo de contacto", store=True)
    partner_is_company = fields.Boolean(related="partner_id.is_company", string="Es empresa", store=True)
    parent_company_gateway_user_id = fields.Many2one(
        "pf.gateway.company",
        string="Empresa vinculada",
        ondelete="set null",
        index=True,
    )
    company_membership_ids = fields.One2many(
        "pf.gateway.company.membership",
        "user_id",
        string="Membresias de empresas",
    )
    commission_agent_line_ids = fields.One2many(
        "pf.gateway.company.commission.agent",
        "company_gateway_user_id",
        string="Comisionistas",
    )
    commission_agent_total_percentage = fields.Float(
        string="Total comisionistas",
        compute="_compute_commission_agent_total_percentage",
        digits=(16, 4),
    )
    bank_account_ids = fields.One2many("pf.gateway.bank.account", "gateway_user_id", string="Cuentas bancarias")
    transfer_source_ids = fields.One2many("pf.gateway.transfer", "source_user_id", string="Transferencias salientes")
    transfer_destination_ids = fields.One2many("pf.gateway.transfer", "destination_user_id", string="Transferencias entrantes")

    _sql_constraints = [
        ("pf_gateway_user_external_id_uniq", "unique(external_id)", "El external_id del usuario del gateway debe ser único."),
    ]

    @api.depends("full_name", "email", "external_id")
    def _compute_name(self):
        for record in self:
            record.name = record.full_name or record.email or record.external_id

    @api.depends("commission_agent_line_ids.percentage", "commission_agent_line_ids.active")
    def _compute_commission_agent_total_percentage(self):
        for record in self:
            record.commission_agent_total_percentage = sum(
                record.commission_agent_line_ids.filtered("active").mapped("percentage")
            )

    @api.constrains("parent_company_gateway_user_id")
    def _check_parent_company_gateway_user(self):
        for record in self:
            company = record.parent_company_gateway_user_id
            company_cuit = "".join(char for char in str(company.cuit or "") if char.isdigit())
            owner_cuit = "".join(char for char in str(record.cuit_owner or "") if char.isdigit())
            if company and owner_cuit and company_cuit != owner_cuit:
                raise ValidationError(_("La empresa vinculada debe coincidir con el CUIT owner del usuario gateway."))

    def _partner_search_domain_from_gateway_item(self, item):
        vat = item.get("cuit_cuil") or item.get("cuit") or item.get("cuil") or item.get("dni")
        email = item.get("email")
        if vat:
            return [("vat", "=", vat)]
        if email:
            return [("email", "=", email)]
        return []

    def _partner_values_from_gateway_item(self, item):
        full_name = item.get("business_name") or item.get("company_name") or item.get("full_name") or item.get("email")
        is_company = bool(item.get("is_company")) or item.get("type") in ("company", "business", "legal_entity")
        return {
            "name": full_name or str(item.get("id")),
            "company_type": "company" if is_company else "person",
            "email": item.get("email") or False,
            "phone": item.get("phone") or False,
            "vat": item.get("cuit_cuil") or item.get("cuit") or item.get("cuil") or item.get("dni") or False,
        }

    def _find_partner_from_gateway_item(self, item):
        domain = self._partner_search_domain_from_gateway_item(item)
        return self.env["res.partner"].search(domain, limit=1) if domain else self.env["res.partner"]

    def _find_or_create_partner_from_gateway_item(self, item):
        domain = self._partner_search_domain_from_gateway_item(item)
        partner = self.env["res.partner"].search(domain, limit=1) if domain else self.env["res.partner"]
        if partner:
            return partner
        return self.env["res.partner"].create(self._partner_values_from_gateway_item(item))

    def action_sync_users(self):
        self.sync_from_gateway(mode="manual", sync_mode="incremental")
        return True

    def action_create_or_link_partner(self):
        for record in self:
            if record.partner_id:
                continue
            item = {
                "id": record.external_id,
                "email": record.email,
                "full_name": record.full_name or record.name,
                "first_name": record.first_name,
                "last_name": record.last_name,
                "dni": record.dni,
                "cuit_cuil": record.cuit_cuil,
                "phone": record.phone,
            }
            record.partner_id = record._find_or_create_partner_from_gateway_item(item)
        return True

    def action_add_costoapp_commission_agent(self):
        self.ensure_one()
        if not self.partner_id.is_company:
            raise ValidationError(_("Sólo los usuarios gateway vinculados a empresas pueden tener comisionistas."))

        costoapp = self.env.ref(
            "pagoflex_wallet_gateway.partner_costoapp_commission_agent",
            raise_if_not_found=False,
        )
        if not costoapp:
            raise ValidationError(_("No se encontró el contacto comisionista CostoAPP."))

        existing = self.commission_agent_line_ids.filtered(lambda line: line.agent_partner_id == costoapp)
        if existing:
            existing.write({"active": True})
        else:
            self.env["pf.gateway.company.commission.agent"].create(
                {
                    "company_gateway_user_id": self.id,
                    "company_partner_id": self.partner_id.id,
                    "agent_partner_id": costoapp.id,
                    "percentage": costoapp.gateway_min_commission_percentage,
                }
            )
        return True

    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        updated_since = None
        if sync_mode == "incremental":
            updated_since = self.search([], order="source_updated_at desc", limit=1).source_updated_at

        log = self.env["pf.gateway.sync.log"].create(
            {
                "name": f"Sincronizar usuarios ({sync_mode})",
                "resource": "users",
                "mode": mode,
                "job_id": job.id if job else False,
            }
            )
        try:
            items = self._gateway_paginated_get("/admin/gateway/users", updated_since=updated_since)
            for item in items:
                external_id = str(item.get("id"))
                record = self.search([("external_id", "=", external_id)], limit=1)
                partner = record.partner_id if record else self.env["res.partner"]
                if not partner:
                    partner = self._find_partner_from_gateway_item(item)

                values = {
                    "external_id": external_id,
                    "active": item.get("is_active", True),
                    "email": item.get("email"),
                    "full_name": item.get("full_name"),
                    "first_name": item.get("first_name"),
                    "last_name": item.get("last_name"),
                    "birth_date": self._coerce_date(item.get("birth_date"), field_name="birth_date"),
                    "dni": item.get("dni"),
                    "gender": item.get("gender"),
                    "cuit_cuil": item.get("cuit_cuil"),
                    "cuit_owner": item.get("cuit_owner"),
                    "phone": item.get("phone"),
                    "nationality": item.get("nationality"),
                    "occupation": item.get("occupation"),
                    "marital_status": item.get("marital_status"),
                    "location": item.get("location"),
                    "is_email_verified": item.get("is_email_verified", False),
                    "is_kyc_verified": item.get("is_kyc_verified", False),
                    "source_created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
                    "source_updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self._payload_to_text(item),
                }
                if partner:
                    values["partner_id"] = partner.id
                if record:
                    record.write(values)
                else:
                    self.create(values)

            log.write(
                {
                    "status": "success",
                    "finished_at": fields.Datetime.now(),
                    "records_processed": len(items),
                    "message": f"Usuarios sincronizados: {len(items)}",
                }
            )
            return len(items)
        except Exception as exc:
            log.write(
                {
                    "status": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_detail": str(exc),
                    "message": "La sincronización de usuarios fallo.",
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
