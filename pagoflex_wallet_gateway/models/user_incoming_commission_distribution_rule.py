import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class PfGatewayUserIncomingCommissionDistributionRule(models.Model):
    _name = "pf.gateway.user.incoming.commission.distribution.rule"
    _description = "Regla de distribucion de comision de transferencias entrantes por usuario"
    _inherit = "pf.gateway.client.mixin"
    _order = "settings_id, name, destination_bank_account_id"

    _gateway_push_fields = {
        "settings_id",
        "destination_bank_account_id",
        "name",
        "commission_percentage",
        "is_active",
    }

    name = fields.Char(string="Nombre")
    settings_id = fields.Many2one(
        "pf.gateway.user.incoming.commission.settings",
        string="Configuración base",
        required=True,
        ondelete="cascade",
        index=True,
    )
    destination_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="ID cuenta destino",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('status', '=', 'active')]",
    )
    destination_cvu_cbu = fields.Char(string="CVU/CBU destino", related="destination_bank_account_id.cvu_cbu", store=False)
    commission_percentage = fields.Float(string="Porcentaje", digits=(16, 4), default=0.0)
    is_active = fields.Boolean(string="Activo", default=True, index=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(readonly=True)
    gateway_user_id = fields.Many2one(
        related="settings_id.gateway_user_id",
        string="Usuario gateway",
        readonly=True,
        store=True,
        index=True,
    )
    destination_user_display_name = fields.Char(
        related="destination_bank_account_id.user_display_name",
        string="Usuario del Gateway",
        readonly=True,
        store=False,
    )
    app_name = fields.Selection(
        related="settings_id.app_name",
        readonly=True,
    )

    _sql_constraints = [
        (
            "ck_pf_gateway_user_itc_dist_rules_pct_nonneg",
            "check(commission_percentage >= 0)",
            "El porcentaje de comisión no puede ser negativo.",
        ),
    ]

    @api.model
    def _get_fallback_name_from_account(self, destination_bank_account_id):
        if not destination_bank_account_id:
            return False
        account = self.env["pf.gateway.bank.account"].browse(destination_bank_account_id)
        if not account:
            return False
        user = account.gateway_user_id
        fallback = user.gateway_display_name or user.full_name or user.name or user.email or user.external_id
        return (fallback or "").strip() or False

    def _get_effective_name(self):
        self.ensure_one()
        return (self.name or "").strip() or self._get_fallback_name_from_account(self.destination_bank_account_id.id) or ""

    @api.onchange("destination_bank_account_id")
    def _onchange_destination_bank_account_id_set_name_fallback(self):
        for record in self:
            if (record.name or "").strip():
                continue
            record.name = record._get_fallback_name_from_account(record.destination_bank_account_id.id) or False

    @api.constrains("commission_percentage")
    def _check_commission_percentage(self):
        for record in self:
            if float_compare(record.commission_percentage, 0.0, precision_digits=4) < 0:
                raise ValidationError(_("El porcentaje de comisión no puede ser negativo."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        settings_model = self.env["pf.gateway.user.incoming.commission.settings"]
        ctx = self.env.context

        for vals in vals_list:
            prepared_vals = dict(vals)
            if not prepared_vals.get("settings_id"):
                settings_id = ctx.get("default_settings_id")

                if not settings_id:
                    gateway_user_id = ctx.get("default_gateway_user_id")
                    app_name = ctx.get("default_app_name")
                    if gateway_user_id:
                        domain = [("gateway_user_id", "=", gateway_user_id)]
                        if app_name:
                            domain.append(("app_name", "=", app_name))
                        settings_id = settings_model.search(domain, order="id", limit=1).id

                if settings_id:
                    prepared_vals["settings_id"] = settings_id

            if not (prepared_vals.get("name") or "").strip():
                fallback_name = self._get_fallback_name_from_account(prepared_vals.get("destination_bank_account_id"))
                if fallback_name:
                    prepared_vals["name"] = fallback_name

            prepared_vals_list.append(prepared_vals)

        records = super().create(prepared_vals_list)
        if self.env.context.get("skip_gateway_push") or self.env.context.get("install_mode"):
            return records

        records_to_push = self.env[self._name]
        for record, values in zip(records, prepared_vals_list):
            if self._gateway_push_fields.intersection(values.keys()):
                records_to_push |= record

        if records_to_push:
            records_to_push._push_batch_to_gateway()
        return records

    def write(self, vals):
        vals = dict(vals)
        if not (vals.get("name") or "").strip():
            destination_id = vals.get("destination_bank_account_id")
            if destination_id and len(self) == 1:
                fallback_name = self._get_fallback_name_from_account(destination_id)
                if fallback_name:
                    vals["name"] = fallback_name

        should_push = (
            bool(self._gateway_push_fields.intersection(vals.keys()))
            and not self.env.context.get("skip_gateway_push")
            and not self.env.context.get("install_mode")
        )
        result = super().write(vals)
        if should_push:
            self._push_batch_to_gateway()
        return result

    def _get_destination_bank_account(self):
        self.ensure_one()
        return self.destination_bank_account_id or self.env["pf.gateway.bank.account"].browse()

    def _rule_payload(self):
        self.ensure_one()
        destination_account = self._get_destination_bank_account()
        return {
            "destination_cvu_cbu": destination_account.cvu_cbu or "",
            "name": self._get_effective_name(),
            "commission_percentage": round(self.commission_percentage or 0.0, 4),
            "is_active": self.is_active,
        }

    def _is_gateway_payload_ready(self):
        self.ensure_one()
        return bool(
            self.settings_id
            and self.destination_bank_account_id
            and self.destination_bank_account_id.external_id
        )

    def _validate_push_preconditions(self):
        self.ensure_one()
        if not self.settings_id:
            raise ValidationError(_("Debe indicar la configuración base antes de actualizar la regla en el gateway."))
        if not self.settings_id.gateway_user_id or not self.settings_id.gateway_user_id.external_id:
            raise ValidationError(_("La configuración base debe tener un usuario antes de actualizar la regla en el gateway."))
        if not (self.settings_id.app_name or "").strip():
            raise ValidationError(_("La configuración base debe tener una app antes de actualizar la regla en el gateway."))
        if not self.destination_bank_account_id:
            raise ValidationError(_("Debe indicar la cuenta destino antes de actualizar la regla en el gateway."))

        destination_account = self._get_destination_bank_account()
        if not destination_account.external_id:
            raise ValidationError(_("La cuenta destino debe tener external_id para actualizar en el gateway."))
        if not destination_account.cvu_cbu:
            raise ValidationError(_("La cuenta destino debe tener CVU/CBU para actualizar en el gateway."))
        if float_compare(self.commission_percentage, 0.0, precision_digits=4) < 0:
            raise ValidationError(_("El porcentaje de comisión no puede ser negativo."))

    def _batch_payload(self):
        self.ensure_one()
        rules = self.search([("settings_id", "=", self.settings_id.id)])
        rules = rules.filtered(lambda rule: rule._is_gateway_payload_ready())
        if not rules:
            return {}

        unique_rules = []
        seen_destinations = set()
        for rule in rules.sorted(key=lambda item: item.id or 0):
            rule._validate_push_preconditions()
            destination_cvu = (rule.destination_bank_account_id.cvu_cbu or "").strip()
            destination_key = destination_cvu or f"account_id:{rule.destination_bank_account_id.id}"
            if destination_key in seen_destinations:
                continue
            seen_destinations.add(destination_key)
            unique_rules.append(rule)

        return {
            "user_id": self.settings_id.gateway_user_id.external_id or "",
            "app_name": self.settings_id.app_name,
            "rules": [rule._rule_payload() for rule in unique_rules],
        }

    def _push_to_gateway(self):
        self.ensure_one()
        self._validate_push_preconditions()
        payload = {
            "user_id": self.settings_id.gateway_user_id.external_id or "",
            "app_name": self.settings_id.app_name,
            "destination_cvu_cbu": self._get_destination_bank_account().cvu_cbu or "",
            "name": self._get_effective_name(),
            "commission_percentage": round(self.commission_percentage or 0.0, 4),
            "is_active": self.is_active,
        }
        response = self._gateway_request_json(
            "PUT",
            "/admin/gateway/user-incoming-transfer-commission/distribution-rules",
            payload=payload,
        )
        self.with_context(skip_gateway_push=True)._apply_gateway_payload(response)

    def _push_batch_to_gateway(self):
        total_pushed = 0
        for settings in self.mapped("settings_id"):
            sample_rule = self.filtered(lambda rule: rule.settings_id == settings)[:1]
            if not sample_rule:
                continue

            payload = sample_rule._batch_payload()
            if not payload:
                continue

            _logger.info("User incoming transfer commission distribution rules batch payload sent to gateway: %s", payload)
            sample_rule._gateway_request_json(
                "PUT",
                "/admin/gateway/user-incoming-transfer-commission/distribution-rules/batch",
                payload=payload,
            )
            total_pushed += len(payload["rules"])

        return total_pushed

    def _apply_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        settings = self._resolve_settings(payload)
        if not settings:
            raise UserError(_("No se pudo resolver la configuración asociada a la regla recibida desde el gateway."))
        destination_account = self._resolve_destination_bank_account(payload)

        values = {
            "settings_id": settings.id,
            "destination_bank_account_id": destination_account.id or self.destination_bank_account_id.id or False,
            "name": payload.get("name") or False,
            "commission_percentage": float(payload.get("commission_percentage") or 0.0),
            "is_active": bool(payload.get("is_active")),
            "created_at": self._coerce_datetime(payload.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(payload.get("updated_at"), field_name="updated_at"),
        }
        self.with_context(skip_gateway_push=True).write(values)

    def _resolve_settings(self, payload):
        settings_model = self.env["pf.gateway.user.incoming.commission.settings"]
        user_uuid = payload.get("user_id")
        app_name = payload.get("app_name")
        if user_uuid and app_name:
            gateway_user = self.env["pf.gateway.user"].search([("external_id", "=", str(user_uuid))], limit=1)
            if gateway_user:
                settings = settings_model.search(
                    [("gateway_user_id", "=", gateway_user.id), ("app_name", "=", app_name)],
                    limit=1,
                )
                if settings:
                    return settings

        return settings_model.browse()

    def _resolve_destination_bank_account(self, payload):
        account_model = self.env["pf.gateway.bank.account"]
        external_id = payload.get("destination_bank_account_id")
        if external_id:
            account = account_model.search([("external_id", "=", str(external_id))], limit=1)
            if account:
                return account

        destination_cvu_cbu = payload.get("destination_cvu_cbu")
        if destination_cvu_cbu:
            return account_model.search([("cvu_cbu", "=", destination_cvu_cbu)], limit=1)

        return account_model.browse()

    def _prepare_values(self, item):
        if not isinstance(item, dict):
            raise UserError(_("La respuesta del gateway contiene reglas inválidas."))

        settings = self._resolve_settings(item)
        destination_account = self._resolve_destination_bank_account(item)

        return {
            "settings_id": settings.id,
            "destination_bank_account_id": destination_account.id or False,
            "name": item.get("name") or False,
            "commission_percentage": float(item.get("commission_percentage") or 0.0),
            "is_active": bool(item.get("is_active")),
            "created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
        }

    def _sync_single_gateway_item(self, item):
        values = self._prepare_values(item)
        if not values.get("settings_id") or not values.get("destination_bank_account_id"):
            return self.browse()

        record = self.search(
            [
                ("settings_id", "=", values["settings_id"]),
                ("destination_bank_account_id", "=", values["destination_bank_account_id"]),
            ],
            limit=1,
        )
        if record:
            record.with_context(skip_gateway_push=True).write(values)
        else:
            record = self.with_context(skip_gateway_push=True).create(values)
        return record

    @api.model
    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None, user_id=None, app_name=None, limit=200, offset=0):
        del mode, sync_mode, job
        path = "/admin/gateway/user-incoming-transfer-commission/distribution-rules"
        page_limit = max(1, int(limit or 200))
        current_offset = max(0, int(offset or 0))
        processed = 0

        while True:
            params = {
                "limit": page_limit,
                "offset": current_offset,
            }
            if user_id:
                params["user_id"] = user_id
            if app_name:
                params["app_name"] = app_name

            payload = self._gateway_request_json("GET", path, params=params)
            items = payload.get("items") if isinstance(payload, dict) else None
            if isinstance(items, list):
                if not items:
                    break
                processed += sum(1 for item in items if self._sync_single_gateway_item(item))
                total = int(payload.get("total") or 0)
                if current_offset + len(items) >= total:
                    break
                if len(items) < page_limit:
                    break
            else:
                processed += 1 if self._sync_single_gateway_item(payload) else 0
                break

            current_offset += page_limit

        return processed
