from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


class PfGatewayIncomingTransferCommissionSettings(models.Model):
    _name = "pf.gateway.incoming.transfer.commission.settings"
    _description = "Configuracion de comision para transferencias entrantes"

    _gateway_push_fields = {"app_name", "default_percentage", "settlement_cvu", "is_active"}

    name = fields.Char(required=True)
    gateway_setting_id = fields.Integer(readonly=True)
    app_name = fields.Char(string="Nombre de la app")
    default_percentage = fields.Float(string="Porcentaje por defecto", digits=(16, 2))
    settlement_bank_account_id = fields.Char(string="ID cuenta bancaria liquidación", readonly=True)
    settlement_cvu = fields.Char(string="CVU de liquidación")
    is_active = fields.Boolean(string="Activo", default=True)
    created_at = fields.Datetime(readonly=True)
    updated_at = fields.Datetime(readonly=True)
    last_sync_at = fields.Datetime(string="Última sincronización", readonly=True)
    distribution_rule_ids = fields.One2many(
        "pf.gateway.incoming.transfer.commission.distribution.rule",
        "setting_id",
        string="Reglas de distribución",
    )

    _inherit = "pf.gateway.client.mixin"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self.env.context.get("skip_gateway_push") or self.env.context.get("install_mode"):
            return records

        for record, values in zip(records, vals_list):
            if self._gateway_push_fields.intersection(values.keys()) and record._is_gateway_payload_ready():
                record._push_to_gateway(propagate_to_accounts=False)
        return records

    def write(self, vals):
        changed_gateway_fields = self._gateway_push_fields.intersection(vals.keys())
        # Ya no propagamos el default_percentage a las cuentas
        changed_default_percentage = False
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
            result = super(
                PfGatewayIncomingTransferCommissionSettings,
                self.with_context(skip_gateway_push=True),
            ).write(vals)
        else:
            result = super().write(vals)
        if should_push:
            for record in self:
                if record._is_gateway_payload_ready():
                    record._push_to_gateway(propagate_to_accounts=False)
        if should_push_rules:
            for record in self:
                record._push_distribution_rules_to_gateway()
        return result

    @api.constrains("default_percentage")
    def _check_default_percentage_supports_company_rules(self):
        for record in self:
            if float_compare(record.default_percentage, 0.0, precision_digits=2) < 0:
                raise ValidationError(_("El porcentaje por defecto no puede ser negativo."))

            line_model = self.env["pf.gateway.company.commission.agent"]
            grouped = line_model.read_group(
                [("active", "=", True)],
                ["percentage:sum"],
                ["company_partner_id"],
            )
            for group in grouped:
                total = group.get("percentage") or 0.0
                if float_compare(total, record.default_percentage, precision_digits=2) > 0:
                    company = self.env["res.partner"].browse(group["company_partner_id"][0])
                    raise ValidationError(
                        _("La empresa %(company)s ya tiene %(total).2f%% asignado a comisionistas; no puede bajar el máximo a %(max).2f%%.")
                        % {
                            "company": company.display_name,
                            "total": total,
                            "max": record.default_percentage,
                        }
                    )

    def _push_payload(self):
        self.ensure_one()
        return {
            "app_name": self.app_name or "",
            "default_percentage": round(self.default_percentage or 0.0, 2),
            "settlement_cvu": self.settlement_cvu or "",
            "is_active": self.is_active,
        }

    def _is_gateway_payload_ready(self):
        self.ensure_one()
        app_name = (self.app_name or "").strip()
        settlement_cvu = (self.settlement_cvu or "").strip()
        return bool(app_name and len(settlement_cvu) >= 22)

    def _validate_push_preconditions(self):
        self.ensure_one()
        app_name = (self.app_name or "").strip()
        settlement_cvu = (self.settlement_cvu or "").strip()

        if not app_name:
            raise ValidationError(_("Debe indicar el nombre de la app antes de actualizar en el gateway."))
        if len(settlement_cvu) < 22:
            raise ValidationError(_("La CVU de liquidación debe tener al menos 22 caracteres para actualizar en el gateway."))

    def _propagate_default_commission_to_app_accounts(self):
        self.ensure_one()
        app_name = (self.app_name or "").strip()
        if not app_name:
            return 0

        bank_accounts = self.env["pf.gateway.bank.account"].search(
            [
                ("app", "=", app_name),
                ("cvu_cbu", "!=", False),
            ]
        )
        if not bank_accounts:
            return 0

        commission_model = self.env["pf.gateway.incoming.transfer.commission.account"]
        commission_accounts = commission_model.search(
            [
                "|",
                ("bank_account_external_id", "in", bank_accounts.mapped("external_id")),
                ("cvu_cbu", "in", bank_accounts.mapped("cvu_cbu")),
            ]
        )
        commission_by_bank_account_id = {
            record.bank_account_external_id: record
            for record in commission_accounts
            if record.bank_account_external_id
        }
        commission_by_cvu = {
            record.cvu_cbu: record
            for record in commission_accounts
            if record.cvu_cbu
        }

        updated = 0
        default_percentage = round(self.default_percentage or 0.0, 2)
        for bank_account in bank_accounts:
            account = (
                commission_by_bank_account_id.get(bank_account.external_id)
                or commission_by_cvu.get(bank_account.cvu_cbu)
            )
            current_percentage = (
                round(account.commission_percentage or 0.0, 2)
                if account
                else default_percentage
            )
            new_percentage = min(current_percentage, default_percentage)
            payload = {
                "cvu_cbu": bank_account.cvu_cbu,
                "commission_percentage": new_percentage,
                "is_active": account.is_active if account else True,
            }
            response = self._gateway_request_json(
                "POST",
                "/admin/gateway/incoming-transfer-commission/accounts",
                params={"app_name": app_name},
                payload=payload,
            )
            commission_model._upsert_items([response])
            updated += 1

        return updated

    def _push_to_gateway(self, *, propagate_to_accounts=False):
        self.ensure_one()
        self._validate_push_preconditions()
        response = self._gateway_request_json(
            "POST",
            "/admin/gateway/incoming-transfer-commission/settings",
            payload=self._push_payload(),
        )
        self.with_context(skip_gateway_push=True)._apply_gateway_payload(response)

        propagated = 0
        if propagate_to_accounts:
            propagated = self._propagate_default_commission_to_app_accounts()

        return propagated

    def _push_distribution_rules_to_gateway(self):
        self.ensure_one()
        app_name = (self.app_name or "").strip()
        if not app_name:
            return 0
        rules = self.distribution_rule_ids.filtered(lambda rule: rule._is_gateway_payload_ready())
        if not rules:
            return 0
        return rules._push_batch_to_gateway(app_name)

    def _apply_gateway_payload(self, payload):
        if not isinstance(payload, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        values = {
            "gateway_setting_id": payload.get("id") or 0,
            "app_name": payload.get("app_name") or False,
            "default_percentage": float(payload.get("default_percentage") or 0.0),
            "settlement_bank_account_id": payload.get("settlement_bank_account_id") or False,
            "settlement_cvu": payload.get("settlement_cvu") or False,
            "is_active": bool(payload.get("is_active")),
            "created_at": self._coerce_datetime(payload.get("created_at"), field_name="created_at"),
            "updated_at": self._coerce_datetime(payload.get("updated_at"), field_name="updated_at"),
            "last_sync_at": fields.Datetime.now(),
        }
        self.with_context(skip_gateway_push=True).write(values)

    def _sync_single_gateway_item(self, item):
        if not isinstance(item, dict):
            raise UserError(_("La respuesta del gateway no tiene el formato esperado."))

        item_id = item.get("id")
        app_name = item.get("app_name")
        if not item_id and not app_name:
            return self.env[self._name]

        domain = []
        if item_id:
            domain = [("gateway_setting_id", "=", item_id)]
        elif app_name:
            domain = [("app_name", "=", app_name)]

        record = self.env[self._name]
        if domain:
            record = self.env[self._name].search(domain, limit=1)

        if not record:
            record_name = (
                _("Comisión %(app)s") % {"app": app_name}
                if app_name
                else _("Comisión gateway %(id)s") % {"id": item_id}
            )
            record = self.env[self._name].with_context(skip_gateway_push=True).create({"name": record_name})

        record._apply_gateway_payload(item)
        return record

    @api.model
    def sync_from_gateway(self, mode="manual", sync_mode="incremental", job=None):
        del mode, sync_mode, job
        payload = self._gateway_request_json(
            "GET", "/admin/gateway/incoming-transfer-commission/settings"
        )

        synced_count = 0
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            for item in payload.get("items"):
                if self._sync_single_gateway_item(item):
                    synced_count += 1
        else:
            # Backward compatibility for endpoints returning a single object.
            synced_count = 1 if self._sync_single_gateway_item(payload) else 0

        return synced_count

    def action_sync_from_gateway(self):
        self.ensure_one()
        synced_count = self.sync_from_gateway(mode="manual", sync_mode="incremental", job=False)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisión sincronizada"),
                "message": _("Se sincronizaron %(count)s configuraciones desde el gateway.") % {"count": synced_count},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_open_push_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Actualizar comisión en gateway"),
            "res_model": "pf.gateway.incoming.transfer.commission.push.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_setting_id": self.id,
                "default_new_default_percentage": self.default_percentage,
            },
        }

    def action_push_to_gateway(self, propagate_to_accounts=False):
        self.ensure_one()
        propagated = self._push_to_gateway(propagate_to_accounts=propagate_to_accounts)
        pushed_rules = self._push_distribution_rules_to_gateway()

        message = _("La configuración de comisión se envió correctamente al gateway.")
        if pushed_rules:
            message = _(
                "La configuración de comisión y %(rules)s reglas de distribución se enviaron correctamente al gateway."
            ) % {"rules": pushed_rules}
        if propagate_to_accounts:
            if pushed_rules:
                message = _(
                    "La configuración, %(rules)s reglas de distribución y %(count)s cuentas asociadas a la app se actualizaron correctamente en el gateway."
                ) % {"rules": pushed_rules, "count": propagated}
            else:
                message = _(
                    "La configuración se envió al gateway y se actualizaron %(count)s cuentas asociadas a la app con el menor valor entre su comisión actual y la comisión por defecto."
                ) % {"count": propagated}

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comisión actualizada"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
