from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PfGatewayUserIncomingCommissionSettings(models.Model):
    _name = "pf.gateway.user.incoming.commission.settings"
    _description = "Configuracion de comision de transferencias entrantes por usuario"
    _inherit = "pf.gateway.client.mixin"
    _order = "app_name, gateway_user_id, id"

    _gateway_push_fields = {"gateway_user_id", "app_name", "total_percentage", "settlement_bank_account_id", "is_active"}

    name = fields.Char(compute="_compute_name", store=True)
    gateway_user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario gateway",
        required=True,
        ondelete="restrict",
        index=True,
    )
    app_name = fields.Selection(
        [
            ("pagoflex", "Pagoflex"),
            ("sivep", "SIVEP"),
        ],
        string="Nombre de la app",
        required=True,
        default="pagoflex",
        index=True,
    )
    total_percentage = fields.Float(string="Porcentaje total", digits=(16, 4), default=0.0)
    settlement_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta bancaria liquidación",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('app', '=', app_name), ('status', '=', 'active')]",
    )
    settlement_cvu = fields.Char(string="CVU de liquidación", related="settlement_bank_account_id.cvu_cbu", store=False)
    is_active = fields.Boolean(string="Activo", default=True, index=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(readonly=True)
    distribution_rule_ids = fields.One2many(
        "pf.gateway.user.incoming.commission.distribution.rule",
        "settings_id",
        string="Reglas de distribución",
    )
    distribution_rules_total_percentage = fields.Float(
        string="Total reglas",
        digits=(16, 4),
        compute="_compute_distribution_rules_total_percentage",
        store=False,
    )

    _sql_constraints = [
        (
            "uq_pf_gateway_user_incoming_commission_settings_user_app",
            "unique(gateway_user_id, app_name)",
            "La configuración de comisión por usuario debe ser única por usuario y aplicación.",
        ),
        (
            "ck_pf_gateway_user_itc_settings_total_pct_nonneg",
            "check(total_percentage >= 0)",
            "El porcentaje total no puede ser negativo.",
        ),
    ]

    @api.depends("gateway_user_id", "app_name")
    def _compute_name(self):
        for record in self:
            record.name = " / ".join(filter(None, [record.app_name, record.gateway_user_id.name])) or False

    @api.depends("distribution_rule_ids.commission_percentage")
    def _compute_distribution_rules_total_percentage(self):
        for record in self:
            record.distribution_rules_total_percentage = sum(record.distribution_rule_ids.mapped("commission_percentage"))

    @api.constrains("total_percentage")
    def _check_total_percentage(self):
        for record in self:
            if float_compare(record.total_percentage, 0.0, precision_digits=4) < 0:
                raise ValidationError(_("El porcentaje total no puede ser negativo."))

    @api.constrains("total_percentage", "distribution_rule_ids", "distribution_rule_ids.commission_percentage")
    def _check_distribution_rules_total_not_exceed_total_percentage(self):
        for record in self:
            rules_total = sum(record.distribution_rule_ids.mapped("commission_percentage"))
            if float_compare(rules_total, record.total_percentage or 0.0, precision_digits=4) > 0:
                raise ValidationError(
                    _(
                        "La suma de reglas (%(rules)s) no puede superar la comisión madre (%(total)s)."
                    )
                    % {
                        "rules": f"{rules_total:.4f}",
                        "total": f"{(record.total_percentage or 0.0):.4f}",
                    }
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_push") or self.env.context.get("install_mode"):
            return records

        for record, values in zip(records, vals_list):
            if self._gateway_push_fields.intersection(values.keys()) and record._is_gateway_payload_ready():
                record._push_to_gateway(propagate_rules=False)
        return records

    def write(self, vals):
        changed_gateway_fields = self._gateway_push_fields.intersection(vals.keys())
        should_push_rules = (
            "distribution_rule_ids" in vals
            and not self.env.context.get("skip_gateway_push")
            and not self.env.context.get("install_mode")
        )
        should_push = (
            bool(changed_gateway_fields)
            and not self.env.context.get("skip_gateway_push")
            and not self.env.context.get("install_mode")
        )

        if should_push_rules:
            result = super(PfGatewayUserIncomingCommissionSettings, self.with_context(skip_gateway_push=True)).write(vals)
        else:
            result = super().write(vals)

        if should_push:
            for record in self:
                if record._is_gateway_payload_ready():
                    record._push_to_gateway(propagate_rules=False)

        if should_push_rules:
            for record in self:
                record._push_distribution_rules_to_gateway()

        return result

    def _get_settlement_bank_account(self):
        self.ensure_one()
        return self.settlement_bank_account_id or self.env["pf.gateway.bank.account"].browse()

    def _resolve_settlement_bank_account(self, settlement_external_id=None, settlement_cvu=None):
        account_model = self.env["pf.gateway.bank.account"]
        if settlement_external_id:
            account = account_model.search([("external_id", "=", str(settlement_external_id))], limit=1)
            if account:
                return account
        if settlement_cvu:
            account = account_model.search([("cvu_cbu", "=", settlement_cvu)], limit=1)
            if account:
                return account
        return account_model.browse()

    def _push_payload(self):
        self.ensure_one()
        settlement_account = self._get_settlement_bank_account()
        return {
            "user_id": self.gateway_user_id.external_id or "",
            "app_name": self.app_name or "pagoflex",
            "total_percentage": round(self.total_percentage or 0.0, 4),
            "settlement_cvu": settlement_account.cvu_cbu or "",
            "is_active": self.is_active,
        }

    def _is_gateway_payload_ready(self):
        self.ensure_one()
        return bool(
            self.gateway_user_id
            and self.gateway_user_id.external_id
            and (self.app_name or "").strip()
            and self.settlement_bank_account_id
            and self.settlement_bank_account_id.external_id
        )

    def _validate_push_preconditions(self):
        self.ensure_one()
        if not self.gateway_user_id or not self.gateway_user_id.external_id:
            raise ValidationError(_("Debe indicar el usuario antes de actualizar la configuración en el gateway."))
        if not (self.app_name or "").strip():
            raise ValidationError(_("Debe indicar el nombre de la app antes de actualizar la configuración en el gateway."))
        if not self.settlement_bank_account_id:
            raise ValidationError(_("Debe indicar la cuenta de liquidación antes de actualizar la configuración en el gateway."))

        settlement_account = self._get_settlement_bank_account()
        if not settlement_account.external_id:
            raise ValidationError(_("La cuenta de liquidación debe tener external_id para actualizar en el gateway."))
        if not settlement_account.cvu_cbu:
            raise ValidationError(_("La cuenta de liquidación debe tener CVU/CBU para actualizar en el gateway."))
        if float_compare(self.total_percentage, 0.0, precision_digits=4) < 0:
            raise ValidationError(_("El porcentaje total no puede ser negativo."))

    def _push_to_gateway(self, *, propagate_rules=False):
        self.ensure_one()
        self._validate_push_preconditions()
        response = self._gateway_request_json(
            "PUT",
            "/admin/gateway/user-incoming-transfer-commission/settings",
            payload=self._push_payload(),
        )
        self.with_context(skip_gateway_push=True)._apply_gateway_payload(response)

        pushed_rules = 0
        if propagate_rules:
            pushed_rules = self._push_distribution_rules_to_gateway()
        return pushed_rules

    def _push_distribution_rules_to_gateway(self):
        self.ensure_one()
        app_name = (self.app_name or "").strip()
        if not app_name:
            return 0

        rules = self.distribution_rule_ids.filtered(lambda rule: rule._is_gateway_payload_ready())
        if not rules:
            return 0
        return rules._push_batch_to_gateway()

    def _resolve_gateway_user(self, user_uuid):
        if not user_uuid:
            return self.env["pf.gateway.user"].browse()
        return self.env["pf.gateway.user"].search([("external_id", "=", str(user_uuid))], limit=1)

    def _apply_gateway_payload(self, payload):
        self.ensure_one()
        if not isinstance(payload, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        gateway_user = self._resolve_gateway_user(payload.get("user_id"))
        settlement_account = self._resolve_settlement_bank_account(
            settlement_external_id=payload.get("settlement_bank_account_id"),
            settlement_cvu=payload.get("settlement_cvu"),
        )
        values = {
            "gateway_user_id": gateway_user.id or False,
            "app_name": payload.get("app_name") or False,
            "total_percentage": float(payload.get("total_percentage") or 0.0),
            "settlement_bank_account_id": settlement_account.id or self.settlement_bank_account_id.id or False,
            "is_active": bool(payload.get("is_active")),
            "created_at": self._coerce_datetime(payload.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(payload.get("updated_at"), field_name="updated_at"),
        }
        self.with_context(skip_gateway_push=True).write(values)

    def _sync_single_gateway_item(self, item):
        if not isinstance(item, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        user_uuid = item.get("user_id")
        app_name = item.get("app_name")
        if not user_uuid or not app_name:
            return self.env[self._name]

        gateway_user = self._resolve_gateway_user(user_uuid)
        if not gateway_user:
            return self.env[self._name]

        settlement_account = self._resolve_settlement_bank_account(
            settlement_external_id=item.get("settlement_bank_account_id"),
            settlement_cvu=item.get("settlement_cvu"),
        )
        if not settlement_account:
            return self.env[self._name]

        domain = [("gateway_user_id", "=", gateway_user.id), ("app_name", "=", app_name)]
        record = self.search(domain, limit=1)
        if not record:
            record = self.with_context(skip_gateway_push=True).create(
                {
                    "gateway_user_id": gateway_user.id,
                    "app_name": app_name,
                    "settlement_bank_account_id": settlement_account.id,
                    "total_percentage": float(item.get("total_percentage") or 0.0),
                    "is_active": bool(item.get("is_active")),
                }
            )

        record._apply_gateway_payload(item)
        return record

    @api.model
    def sync_from_gateway(self, user_id=None, app_name=None, limit=200, offset=0):
        path = "/admin/gateway/user-incoming-transfer-commission/settings"
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
