import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


_logger = logging.getLogger(__name__)


class PfGatewayIncomingTransferCommissionDistributionRule(models.Model):
    _name = "pf.gateway.incoming.transfer.commission.distribution.rule"
    _description = "Regla de distribucion de comision de transferencias entrantes"
    _inherit = "pf.gateway.client.mixin"
    _order = "app_name, name, destination_cvu_cbu"

    _gateway_push_fields = {
        "app_name",
        "destination_cvu_cbu",
        "commission_percentage",
        "name",
        "is_active",
    }

    name = fields.Char(string="Nombre")
    active = fields.Boolean(default=True)
    gateway_rule_id = fields.Integer(string="ID regla gateway", readonly=True, index=True)
    setting_id = fields.Many2one(
        "pf.gateway.incoming.transfer.commission.settings",
        string="Configuración base",
        ondelete="set null",
        index=True,
    )
    gateway_setting_id = fields.Integer(string="ID configuración gateway", readonly=True, index=True)
    app_name = fields.Char(string="Nombre de la app", index=True)
    destination_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta destino",
        ondelete="set null",
    )
    destination_bank_account_external_id = fields.Char(string="ID cuenta destino gateway", readonly=True, index=True)
    destination_cvu_cbu = fields.Char(string="CVU/CBU destino", index=True)
    commission_percentage = fields.Float(string="Porcentaje", digits=(16, 2), default=0.0)
    is_active = fields.Boolean(string="Activo", default=True, index=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(index=True, readonly=True)
    last_sync_at = fields.Datetime(index=True, readonly=True)
    raw_payload = fields.Text()
    user_display_name = fields.Char(
        string="Usuario",
        related="destination_bank_account_id.user_display_name",
        store=False,
    )

    @api.onchange("setting_id")
    def _onchange_setting_id(self):
        for record in self:
            if record.setting_id and not record.app_name:
                record.app_name = record.setting_id.app_name

    @api.onchange("destination_bank_account_id")
    def _onchange_destination_bank_account_id(self):
        for record in self:
            if record.destination_bank_account_id:
                record.destination_cvu_cbu = record.destination_bank_account_id.cvu_cbu

    @api.constrains("commission_percentage")
    def _check_commission_percentage(self):
        for record in self:
            if float_compare(record.commission_percentage, 0.0, precision_digits=2) < 0:
                raise ValidationError(_("El porcentaje de distribución no puede ser negativo."))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._fill_values_from_relations(values)

        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_push") or self.env.context.get("install_mode"):
            return records

        records_to_push = self.browse()
        for record, values in zip(records, vals_list):
            if self._gateway_push_fields.intersection(values.keys()) and record._is_gateway_payload_ready():
                records_to_push |= record
        if records_to_push:
            records_to_push._push_apps_to_gateway()
        return records

    def write(self, vals):
        self._fill_values_from_relations(vals)
        should_push = (
            bool(self._gateway_push_fields.intersection(vals.keys()))
            and not self.env.context.get("skip_gateway_push")
            and not self.env.context.get("install_mode")
        )
        result = super().write(vals)
        if should_push:
            records_to_push = self.filtered(lambda record: record._is_gateway_payload_ready())
            if records_to_push:
                records_to_push._push_apps_to_gateway()
        return result

    def _fill_values_from_relations(self, values):
        if values.get("setting_id") and not values.get("app_name"):
            setting = self.env["pf.gateway.incoming.transfer.commission.settings"].browse(values["setting_id"])
            if setting.exists():
                values["app_name"] = setting.app_name
        if values.get("destination_bank_account_id") and not values.get("destination_cvu_cbu"):
            account = self.env["pf.gateway.bank.account"].browse(values["destination_bank_account_id"])
            if account.exists():
                values["destination_cvu_cbu"] = account.cvu_cbu

    def _rule_payload(self):
        self.ensure_one()
        return {
            "destination_cvu_cbu": self.destination_cvu_cbu or "",
            "commission_percentage": round(self.commission_percentage or 0.0, 2),
            "name": self.name or "",
            "is_active": self.is_active,
        }

    def _is_gateway_payload_ready(self):
        self.ensure_one()
        return bool((self.app_name or "").strip() and (self.destination_cvu_cbu or "").strip())

    def _validate_push_preconditions(self):
        self.ensure_one()
        if not (self.app_name or "").strip():
            raise ValidationError(_("Debe indicar el nombre de la app antes de actualizar la regla en el gateway."))
        if not (self.destination_cvu_cbu or "").strip():
            raise ValidationError(_("Debe indicar el CVU/CBU destino antes de actualizar la regla en el gateway."))
        if float_compare(self.commission_percentage, 0.0, precision_digits=2) < 0:
            raise ValidationError(_("El porcentaje de distribución no puede ser negativo."))

    def _batch_payload(self, app_name):
        rules = self.filtered(lambda rule: (rule.app_name or "").strip() == app_name and rule._is_gateway_payload_ready())
        if not rules:
            return {}
        rules_by_destination = {}
        for rule in rules.sorted(key=lambda item: item.id or 0):
            rule._validate_push_preconditions()
            rules_by_destination[rule.destination_cvu_cbu] = rule
        return {
            "app_name": app_name,
            "rules": [rule._rule_payload() for rule in rules_by_destination.values()],
        }

    def _push_batch_to_gateway(self, app_name):
        app_name = (app_name or "").strip()
        payload = self._batch_payload(app_name)
        if not payload:
            return 0
        _logger.info(
            "Incoming transfer commission distribution rules batch payload sent to gateway: %s",
            payload,
        )
        self._gateway_request_json(
            "POST",
            "/admin/gateway/incoming-transfer-commission/distribution-rules/batch",
            payload=payload,
        )
        return len(payload["rules"])

    def _push_apps_to_gateway(self):
        pushed = 0
        app_names = sorted({(record.app_name or "").strip() for record in self if (record.app_name or "").strip()})
        model = self.env[self._name]
        for app_name in app_names:
            app_rules = model.search([("app_name", "=", app_name)])
            pushed += app_rules._push_batch_to_gateway(app_name)
        return pushed

    def _resolve_setting(self, payload):
        settings_model = self.env["pf.gateway.incoming.transfer.commission.settings"]
        gateway_setting_id = payload.get("settings_id") or payload.get("setting_id")
        if gateway_setting_id:
            setting = settings_model.search([("gateway_setting_id", "=", int(gateway_setting_id))], limit=1)
            if setting:
                return setting

        app_name = payload.get("app_name")
        if app_name:
            return settings_model.search([("app_name", "=", app_name)], limit=1)

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

        setting = self._resolve_setting(item)
        destination_account = self._resolve_destination_bank_account(item)
        gateway_setting_id = item.get("settings_id") or item.get("setting_id") or setting.gateway_setting_id

        return {
            "gateway_rule_id": item.get("id") or False,
            "active": True,
            "setting_id": setting.id,
            "gateway_setting_id": gateway_setting_id or False,
            "app_name": item.get("app_name") or setting.app_name or False,
            "destination_bank_account_id": destination_account.id,
            "destination_bank_account_external_id": item.get("destination_bank_account_id") or False,
            "destination_cvu_cbu": item.get("destination_cvu_cbu") or destination_account.cvu_cbu or False,
            "name": item.get("name") or False,
            "commission_percentage": float(item.get("commission_percentage") or 0.0),
            "is_active": bool(item.get("is_active")),
            "created_at": self._coerce_datetime(item.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(item.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
            "raw_payload": self._payload_to_text(item),
        }

    def _apply_gateway_payload(self, payload):
        if not isinstance(payload, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        values = self._prepare_values(payload)
        self.with_context(skip_gateway_push=True).write(values)

    def _sync_single_gateway_item(self, item):
        values = self._prepare_values(item)
        domain = [
            ("app_name", "=", values.get("app_name")),
            ("destination_cvu_cbu", "=", values.get("destination_cvu_cbu")),
        ]
        if not values.get("app_name") or not values.get("destination_cvu_cbu"):
            return self.browse()

        record = self.browse()
        existing = self.search(domain, order="id")
        if existing:
            record = existing[0]
            duplicates = existing - record
            if duplicates:
                duplicates.unlink()

        if record:
            record.with_context(skip_gateway_push=True).write(values)
        else:
            record = self.with_context(skip_gateway_push=True).create(values)
        return record

    def _replace_app_rules_from_gateway(self, app_name, items):
        app_name = (app_name or "").strip()
        if not app_name:
            return 0

        prepared_by_destination = {}
        for item in items:
            values = self._prepare_values(item)
            values["app_name"] = values.get("app_name") or app_name
            destination = (values.get("destination_cvu_cbu") or "").strip()
            if destination:
                prepared_by_destination[destination] = values

        self.search([("app_name", "=", app_name)]).unlink()
        for values in prepared_by_destination.values():
            self.with_context(skip_gateway_push=True).create(values)
        return len(prepared_by_destination)

    @api.model
    def sync_from_gateway(
        self,
        mode="manual",
        sync_mode="full",
        job=None,
        app_name=None,
        destination_cvu_cbu=None,
        is_active=None,
        limit=None,
        offset=0,
    ):
        del mode, sync_mode, job
        path = "/admin/gateway/incoming-transfer-commission/distribution-rules"
        page_limit = max(1, int(limit or self._gateway_page_size()))
        current_offset = max(0, int(offset or 0))
        fetched_items = []

        while True:
            params = {
                "limit": page_limit,
                "offset": current_offset,
            }
            if app_name:
                params["app_name"] = app_name
            if destination_cvu_cbu:
                params["destination_cvu_cbu"] = destination_cvu_cbu
            if is_active is not None:
                params["is_active"] = str(bool(is_active)).lower()

            payload = self._gateway_request_json("GET", path, params=params)
            items = payload.get("items") if isinstance(payload, dict) else None
            if items is None and isinstance(payload, list):
                items = payload
            if items is None and isinstance(payload, dict):
                items = [payload]
            if not isinstance(items, list):
                raise UserError(_("La respuesta del gateway no contiene una lista válida en 'items'."))

            fetched_items.extend(items)

            total = int(payload.get("total") or 0) if isinstance(payload, dict) else 0
            if not items or len(items) < page_limit:
                break
            if total and current_offset + len(items) >= total:
                break

            current_offset += page_limit

        if destination_cvu_cbu:
            processed = 0
            for item in fetched_items:
                if self._sync_single_gateway_item(item):
                    processed += 1
            return processed

        items_by_app = {}
        for item in fetched_items:
            if not isinstance(item, dict):
                continue
            item_app_name = (item.get("app_name") or app_name or "").strip()
            if item_app_name:
                items_by_app.setdefault(item_app_name, []).append(item)

        if app_name and app_name not in items_by_app:
            self.search([("app_name", "=", app_name)]).unlink()
            return 0

        if not app_name:
            self.search([]).unlink()

        processed = 0
        for item_app_name, app_items in items_by_app.items():
            processed += self._replace_app_rules_from_gateway(item_app_name, app_items)
        return processed

    def action_sync_all_from_gateway(self):
        processed = self.env[self._name].sync_from_gateway()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reglas sincronizadas"),
                "message": _("Se procesaron %s reglas de distribución.") % processed,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_sync_this_rule(self):
        self.ensure_one()
        if not self.destination_cvu_cbu:
            raise UserError(_("Esta regla no tiene CVU/CBU destino para sincronizar."))

        processed = self.env[self._name].sync_from_gateway(
            app_name=(self.app_name or "").strip() or None,
            destination_cvu_cbu=self.destination_cvu_cbu,
            limit=1,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Regla sincronizada"),
                "message": _("Se procesaron %s reglas para %s.") % (processed, self.destination_cvu_cbu),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_push_to_gateway(self):
        pushed = self._push_apps_to_gateway()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reglas actualizadas"),
                "message": _("Se enviaron %(count)s reglas de distribución al gateway.") % {"count": pushed},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
