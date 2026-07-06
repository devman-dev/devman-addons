import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class PfGatewayUser(models.Model):
    _name = "pf.gateway.user"
    _description = "Usuario de PagoFlex Gateway"
    _inherit = "pf.gateway.client.mixin"
    _order = "source_updated_at desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    active = fields.Boolean(default=True)
    external_id = fields.Char(index=True)
    email = fields.Char(index=True)
    gateway_display_name = fields.Char(string="Nombre para mostrar", oldname="display_name")
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
    is_email_verified = fields.Boolean(default=True)
    is_kyc_verified = fields.Boolean(default=True)
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
    parent_user_id = fields.Many2one(
        "pf.gateway.user",
        string="Cuenta padre",
        ondelete="set null",
        index=True,
    )
    has_linked_company = fields.Boolean(
        string="Tiene empresa",
        compute="_compute_has_linked_company",
        store=True,
    )
    register_as_company = fields.Boolean(
        string="Registrar como empresa",
        help="Solo se usa al crear en gateway y no se persiste en el usuario.",
    )
    app_name = fields.Selection(
        [
            ("pagoflex", "Pagoflex"),
            ("sivep", "SIVEP"),
        ],
        string="App",
        help="Solo se usa al crear como empresa en gateway y no se persiste en el usuario.",
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
    incoming_commission_setting_ids = fields.One2many(
        "pf.gateway.user.incoming.commission.settings",
        "gateway_user_id",
        string="Configuraciones de comisión entrante",
    )
    incoming_commission_setting_selected_id = fields.Many2one(
        "pf.gateway.user.incoming.commission.settings",
        string="Configuración de comisión entrante seleccionada",
        ondelete="set null",
        copy=False,
    )
    incoming_commission_setting_id = fields.Many2one(
        "pf.gateway.user.incoming.commission.settings",
        string="Configuración de comisión entrante",
        compute="_compute_incoming_commission_setting_id",
        inverse="_inverse_incoming_commission_setting_id",
        store=False,
    )
    incoming_commission_app_name = fields.Selection(
        related="incoming_commission_setting_selected_id.app_name",
        string="Nombre de la app",
        readonly=True,
    )
    incoming_commission_total_percentage = fields.Float(
        related="incoming_commission_setting_selected_id.total_percentage",
        string="Porcentaje total",
        readonly=True,
        digits=(16, 4),
    )
    incoming_commission_rules_total_percentage = fields.Float(
        related="incoming_commission_setting_selected_id.distribution_rules_total_percentage",
        string="Total reglas",
        readonly=True,
        digits=(16, 4),
    )
    incoming_commission_settlement_bank_account_id = fields.Many2one(
        related="incoming_commission_setting_selected_id.settlement_bank_account_id",
        string="Cuenta bancaria liquidación",
        readonly=True,
    )
    incoming_commission_is_active = fields.Boolean(
        related="incoming_commission_setting_selected_id.is_active",
        string="Activo",
        readonly=True,
    )
    incoming_commission_updated_at = fields.Datetime(
        related="incoming_commission_setting_selected_id.updated_at",
        string="Updated At",
        readonly=True,
    )
    incoming_commission_distribution_rule_ids = fields.One2many(
        "pf.gateway.user.incoming.commission.distribution.rule",
        related="incoming_commission_setting_selected_id.distribution_rule_ids",
        string="Reglas de distribución",
        readonly=False,
    )
    bank_account_ids = fields.One2many("pf.gateway.bank.account", "gateway_user_id", string="Cuentas bancarias")
    transfer_source_ids = fields.One2many("pf.gateway.transfer", "source_user_id", string="Transferencias salientes")
    transfer_destination_ids = fields.One2many("pf.gateway.transfer", "destination_user_id", string="Transferencias entrantes")
    statement_line_ids = fields.One2many(
        "pf.gateway.user.statement.line",
        "user_id",
        string="Resumen de cuenta",
        readonly=True,
    )
    statement_status_filter = fields.Selection(
        [
            ("CREATED", "CREATED"),
            ("AUTHORIZED", "AUTHORIZED"),
            ("CAPTURED", "CAPTURED"),
            ("COMPLETED", "COMPLETED"),
            ("FAILED", "FAILED"),
            ("CANCELLED", "CANCELLED"),
        ],
        string="Estado transacción",
        help="Filtra el detalle de movimientos por estado.",
    )
    statement_line_filtered_ids = fields.One2many(
        "pf.gateway.user.statement.line",
        compute="_compute_statement_line_filtered_ids",
        string="Detalle de movimientos filtrado",
        readonly=True,
    )
    statement_summary_ids = fields.One2many(
        "pf.gateway.user.statement.summary",
        "user_id",
        string="Resumen por CVU/App",
        readonly=True,
    )
    statement_line_count = fields.Integer(string="Movimientos", compute="_compute_statement_summary")
    statement_incoming_total = fields.Float(string="Total entradas", compute="_compute_statement_summary", digits=(16, 2))
    statement_outgoing_total = fields.Float(string="Total salidas", compute="_compute_statement_summary", digits=(16, 2))
    statement_net_total = fields.Float(string="Neto", compute="_compute_statement_summary", digits=(16, 2))

    _sql_constraints = [
        ("pf_gateway_user_external_id_uniq", "unique(external_id)", "El external_id del usuario del gateway debe ser único."),
    ]

    @api.depends("gateway_display_name", "full_name", "email", "external_id")
    def _compute_name(self):
        for record in self:
            record.name = record.gateway_display_name or record.full_name or record.email or record.external_id

    @api.depends("commission_agent_line_ids.percentage", "commission_agent_line_ids.active")
    def _compute_commission_agent_total_percentage(self):
        for record in self:
            record.commission_agent_total_percentage = sum(
                record.commission_agent_line_ids.filtered("active").mapped("percentage")
            )

    @api.depends("parent_company_gateway_user_id")
    def _compute_has_linked_company(self):
        for record in self:
            record.has_linked_company = bool(record.parent_company_gateway_user_id)

    @api.depends("incoming_commission_setting_selected_id", "incoming_commission_setting_ids")
    def _compute_incoming_commission_setting_id(self):
        for record in self:
            selected = record.incoming_commission_setting_selected_id
            if selected and selected in record.incoming_commission_setting_ids:
                effective = selected
            else:
                effective = record.incoming_commission_setting_ids[:1]

            record.incoming_commission_setting_id = effective

    def _inverse_incoming_commission_setting_id(self):
        for record in self:
            record.incoming_commission_setting_selected_id = record.incoming_commission_setting_id

    def _ensure_incoming_commission_setting_selected(self):
        for record in self:
            if record.incoming_commission_setting_selected_id:
                continue
            fallback = record.incoming_commission_setting_ids[:1]
            if fallback:
                super(PfGatewayUser, record.with_context(skip_gateway_user_push=True)).write(
                    {"incoming_commission_setting_selected_id": fallback.id}
                )

    def _compute_statement_summary(self):
        line_model = self.env["pf.gateway.user.statement.line"]
        for record in self:
            lines = line_model.search([("user_id", "=", record.id)])
            incoming_total = sum(lines.filtered(lambda line: line.signed_amount > 0).mapped("signed_amount"))
            outgoing_total = -sum(lines.filtered(lambda line: line.signed_amount < 0).mapped("signed_amount"))
            record.statement_line_count = len(lines)
            record.statement_incoming_total = incoming_total
            record.statement_outgoing_total = outgoing_total
            record.statement_net_total = incoming_total - outgoing_total

    @api.depends("statement_status_filter")
    def _compute_statement_line_filtered_ids(self):
        line_model = self.env["pf.gateway.user.statement.line"]
        for record in self:
            domain = [("user_id", "=", record.id)]
            if record.statement_status_filter:
                domain.append(("status", "=", record.statement_status_filter))
            record.statement_line_filtered_ids = line_model.search(domain, order="transaction_at desc, id desc")

    def action_open_account_statement(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Resumen de cuenta - %s") % (self.gateway_display_name or self.name),
            "res_model": "pf.gateway.user.statement.line",
            "view_mode": "list,form,pivot,graph",
            "domain": [("user_id", "=", self.id)],
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
            },
        }

    @api.constrains("parent_company_gateway_user_id")
    def _check_parent_company_gateway_user(self):
        for record in self:
            company = record.parent_company_gateway_user_id
            company_cuit = "".join(char for char in str(company.cuit or "") if char.isdigit())
            owner_cuit = "".join(char for char in str(record.cuit_owner or "") if char.isdigit())
            if company and owner_cuit and company_cuit != owner_cuit:
                raise ValidationError(_("La empresa vinculada debe coincidir con el CUIT owner del usuario gateway."))

    @api.constrains("register_as_company", "app_name")
    def _check_register_as_company_requires_app(self):
        for record in self:
            if record.register_as_company and not record.app_name:
                raise ValidationError(
                    _("Debes seleccionar una app cuando activas 'Registrar como empresa'.")
                )

    @api.constrains("incoming_commission_setting_selected_id")
    def _check_incoming_commission_setting_belongs_to_user(self):
        for record in self:
            selected = record.incoming_commission_setting_selected_id
            selected_owner = selected.gateway_user_id
            if selected and selected_owner and selected_owner.id != record.id:
                raise ValidationError(
                    _("La configuración de comisión seleccionada debe pertenecer al usuario actual.")
                )

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

    def copy(self, default=None):
        default = dict(default or {})
        # Duplicar usuario como borrador para alta manual en gateway.
        default.setdefault("email", False)
        default.setdefault("external_id", False)
        default.setdefault("app_name", False)
        return super().copy(default)

    def action_sync_user_bank_accounts(self):
        bank_account_model = self.env["pf.gateway.bank.account"]
        processed_accounts = bank_account_model.sync_from_gateway(mode="manual", sync_mode="incremental")

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización de cuentas bancarias completada"),
                "message": _(
                    "Se procesaron %(accounts)s cuentas para %(users)s usuario(s)."
                )
                % {
                    "accounts": processed_accounts,
                    "users": len(self),
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_sync_user_commissions(self):
        settings_model = self.env["pf.gateway.user.incoming.commission.settings"]
        rules_model = self.env["pf.gateway.user.incoming.commission.distribution.rule"]
        processed_settings = 0
        processed_rules = 0

        for record in self:
            if not record.external_id:
                raise UserError(_("El usuario debe tener external_id para sincronizar comisiones desde el gateway."))
            processed_settings += settings_model.sync_from_gateway(user_id=record.external_id)
            processed_rules += rules_model.sync_from_gateway(user_id=record.external_id)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sincronización de comisiones completada"),
                "message": _(
                    "Se procesaron %(settings)s configuraciones y %(rules)s reglas para %(users)s usuario(s)."
                )
                % {
                    "settings": processed_settings,
                    "rules": processed_rules,
                    "users": len(self),
                },
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_open_load_default_incoming_commission_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Cargar comision entrante por defecto"),
            "res_model": "pf.gateway.user.incoming.commission.load.default.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_gateway_user_id": self.id,
                "default_app_name": self.incoming_commission_app_name or "pagoflex",
            },
        }

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

    def _gateway_user_payload_from_vals(self, vals):
        parent_user = None
        parent_user_val = vals.get("parent_user_id")
        if isinstance(parent_user_val, models.BaseModel):
            parent_user = parent_user_val
        elif isinstance(parent_user_val, int):
            parent_user = self.browse(parent_user_val)

        payload = {
            "id": vals.get("external_id") or vals.get("id") or None,
            "email": vals.get("email") or None,
            "display_name": vals.get("gateway_display_name") or vals.get("display_name") or None,
            "full_name": vals.get("full_name") or vals.get("name") or None,
            "first_name": vals.get("first_name") or None,
            "last_name": vals.get("last_name") or None,
            "birth_date": vals.get("birth_date").strftime("%Y-%m-%d") if hasattr(vals.get("birth_date"), "strftime") else (vals.get("birth_date") or None),
            "dni": vals.get("dni") or None,
            "gender": vals.get("gender") or None,
            "cuit_cuil": vals.get("cuit_cuil") or None,
            "cuit_owner": vals.get("cuit_owner") or None,
            "phone": vals.get("phone") or None,
            "nationality": vals.get("nationality") or None,
            "occupation": vals.get("occupation") or None,
            "marital_status": vals.get("marital_status") or None,
            "location": vals.get("location") or None,
            "parent_user_id": (
                parent_user.external_id
                if parent_user and parent_user.exists() and parent_user.external_id
                else vals.get("parent_user_external_id")
            )
            or None,
            "is_active": bool(vals.get("active", True)),
            "is_email_verified": vals.get("is_email_verified") if "is_email_verified" in vals else None,
            "is_kyc_verified": vals.get("is_kyc_verified") if "is_kyc_verified" in vals else None,
        }
        # Solo incluir register_as_company si tiene un valor booleano válido (evitar enviar None al gateway)
        register_as_company_val = vals.get("register_as_company") if "register_as_company" in vals else None
        if register_as_company_val is not None:
            payload["register_as_company"] = bool(register_as_company_val)
        # Solo incluir app_name si tiene un valor válido (evitar enviar None al gateway)
        app_name_val = vals.get("app_name") if "app_name" in vals else None
        if app_name_val is not None:
            payload["app_name"] = str(app_name_val)
        return payload

    def _values_from_gateway_item(self, item):
        partner = self._find_partner_from_gateway_item(item)
        parent_external_id = item.get("parent_user_id")
        parent_user = self.search([("external_id", "=", str(parent_external_id))], limit=1) if parent_external_id else self.env["pf.gateway.user"]
        values = {}
        if "id" in item:
            values["external_id"] = str(item.get("id")) if item.get("id") is not None else False
        if "is_active" in item:
            values["active"] = item.get("is_active", True)
        if "email" in item:
            values["email"] = item.get("email")
        if "display_name" in item:
            values["gateway_display_name"] = item.get("display_name")
        if "full_name" in item:
            values["full_name"] = item.get("full_name")
        if "first_name" in item:
            values["first_name"] = item.get("first_name")
        if "last_name" in item:
            values["last_name"] = item.get("last_name")
        if "birth_date" in item:
            values["birth_date"] = self._coerce_date(item.get("birth_date"), field_name="birth_date")
        if "dni" in item:
            values["dni"] = item.get("dni")
        if "gender" in item:
            values["gender"] = item.get("gender")
        if "cuit_cuil" in item:
            values["cuit_cuil"] = item.get("cuit_cuil")
        if "cuit_owner" in item:
            values["cuit_owner"] = item.get("cuit_owner")
        if "phone" in item:
            values["phone"] = item.get("phone")
        if "nationality" in item:
            values["nationality"] = item.get("nationality")
        if "occupation" in item:
            values["occupation"] = item.get("occupation")
        if "marital_status" in item:
            values["marital_status"] = item.get("marital_status")
        if "location" in item:
            values["location"] = item.get("location")
        if "is_email_verified" in item:
            values["is_email_verified"] = item.get("is_email_verified")
        if "is_kyc_verified" in item:
            values["is_kyc_verified"] = item.get("is_kyc_verified")
        if "created_at" in item:
            values["source_created_at"] = self._coerce_datetime(item.get("created_at"), field_name="created_at")
        if "updated_at" in item:
            values["source_updated_at"] = self._coerce_datetime(item.get("updated_at"), field_name="updated_at")
        values["last_sync_at"] = fields.Datetime.now()
        values["parent_user_id"] = parent_user.id if parent_user else False
        values["raw_payload"] = self._payload_to_text(item)
        if partner:
            values["partner_id"] = partner.id
        return values

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("skip_gateway_user_push"):
            return super().create(vals_list)

        prepared_vals_list = []
        for vals in vals_list:
            prepared_vals = dict(vals)
            register_as_company = bool(prepared_vals.pop("register_as_company", False))
            app_name = prepared_vals.pop("app_name", None)

            # If the ID is not set, create the user first in gateway and map response values.
            if not prepared_vals.get("external_id"):
                payload_values = dict(prepared_vals)
                if register_as_company:
                    payload_values["register_as_company"] = True
                    if app_name:
                        payload_values["app_name"] = app_name
                payload = self._gateway_user_payload_from_vals(payload_values)
                response = self._gateway_request_json("POST", "/admin/gateway/users", payload=payload)
                if not isinstance(response, dict):
                    raise UserError(_("El gateway devolvió una respuesta inválida al crear el usuario."))

                user_data = response.get("user") or response
                if not isinstance(user_data, dict):
                    raise UserError(_("El gateway devolvió una respuesta inválida al crear el usuario."))

                mapped_vals = self._values_from_gateway_item(user_data)
                if not mapped_vals.get("external_id"):
                    raise UserError(_("El gateway no devolvió un ID de usuario al crear el registro."))

                for key, value in mapped_vals.items():
                    if key == "external_id":
                        prepared_vals[key] = value
                    elif key not in prepared_vals or prepared_vals.get(key) in (False, None, ""):
                        prepared_vals[key] = value

            prepared_vals_list.append(prepared_vals)

        return super().create(prepared_vals_list)

    def write(self, vals):
        if self.env.context.get("skip_gateway_user_push"):
            return super().write(vals)

        vals = dict(vals)
        if (
            "incoming_commission_distribution_rule_ids" in vals
            and "incoming_commission_setting_selected_id" not in vals
            and len(self) == 1
            and not self.incoming_commission_setting_selected_id
        ):
            fallback = self.incoming_commission_setting_ids[:1]
            if fallback:
                vals["incoming_commission_setting_selected_id"] = fallback.id

        result = super().write(vals)
        self._ensure_incoming_commission_setting_selected()

        # Campos que se sincronizan con el gateway
        gateway_fields = {
            "email", "gateway_display_name", "full_name", "first_name", "last_name", "birth_date",
            "dni", "gender", "cuit_cuil", "cuit_owner", "phone",
            "nationality", "occupation", "marital_status", "location", "active",
            "is_email_verified", "is_kyc_verified", "parent_user_id",
        }
        if not gateway_fields.intersection(vals):
            return result

        for record in self:
            if not record.external_id:
                continue
            payload = self._gateway_user_payload_from_vals({
                **{f: getattr(record, f) for f in gateway_fields},
                "external_id": record.external_id,
                **vals,
            })
            _logger.debug(
                "Gateway user write POST /admin/gateway/users external_id=%s email=%s payload=%s",
                record.external_id,
                record.email,
                payload,
            )
            response = self._gateway_request_json(
                "POST", "/admin/gateway/users", payload=payload
            )
            if isinstance(response, dict):
                user_data = response.get("user") or response
                if isinstance(user_data, dict):
                    mapped_vals = self._values_from_gateway_item(user_data)
                    if "display_name" not in user_data:
                        mapped_vals.pop("gateway_display_name", None)
                    mapped_vals.pop("external_id", None)
                    super(PfGatewayUser, record).write(mapped_vals)

        return result

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
                values = self._values_from_gateway_item(item)
                external_id = values.get("external_id")
                if not external_id:
                    continue
                record = self.search([("external_id", "=", external_id)], limit=1)
                if record:
                    record.with_context(skip_gateway_user_push=True).write(values)
                else:
                    self.with_context(skip_gateway_user_push=True).create(values)

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
