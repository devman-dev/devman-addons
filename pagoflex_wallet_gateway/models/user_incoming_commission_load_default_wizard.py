from odoo import _, fields, models
from odoo.exceptions import UserError


class PfGatewayUserIncomingCommissionLoadDefaultWizard(models.TransientModel):
    _name = "pf.gateway.user.incoming.commission.load.default.wizard"
    _description = "Cargar comision entrante por defecto en usuario"

    gateway_user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario gateway",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    app_name = fields.Selection(
        [
            ("pagoflex", "Pagoflex"),
            ("sivep", "SIVEP"),
        ],
        string="App",
        required=True,
        default="pagoflex",
    )

    def _get_default_settings(self):
        self.ensure_one()
        settings = self.env["pf.gateway.incoming.transfer.commission.settings"].search(
            [("app_name", "=ilike", self.app_name), ("is_active", "=", True)],
            order="id",
        )
        if not settings:
            raise UserError(
                _("No hay una configuracion de comision entrante por defecto activa para la app %s.")
                % self.app_name
            )
        if len(settings) > 1:
            raise UserError(
                _("Hay mas de una configuracion de comision entrante por defecto activa para la app %s.")
                % self.app_name
            )
        return settings

    def _resolve_bank_account(self, *, account=False, external_id=False, cvu_cbu=False, label=False):
        account_model = self.env["pf.gateway.bank.account"]
        account = account if account and account.exists() else account_model.browse()
        if not account and external_id:
            account = account_model.search([("external_id", "=", str(external_id))], limit=1)
        if not account and cvu_cbu:
            account = account_model.search([("cvu_cbu", "=", cvu_cbu)], limit=1)
        if not account:
            raise UserError(
                _("No se encontro una cuenta bancaria local para %(label)s. External ID: %(external)s. CVU/CBU: %(cvu)s.")
                % {
                    "label": label or _("la configuracion"),
                    "external": external_id or "-",
                    "cvu": cvu_cbu or "-",
                }
            )
        return account

    def action_load_defaults(self):
        self.ensure_one()
        user = self.gateway_user_id
        if not user.external_id:
            raise UserError(_("El usuario debe tener external_id para cargar comisiones entrantes."))

        default_settings = self._get_default_settings()
        settlement_account = self._resolve_bank_account(
            external_id=default_settings.settlement_bank_account_id,
            cvu_cbu=default_settings.settlement_cvu,
            label=_("la cuenta de liquidacion"),
        )

        user_settings_model = self.env["pf.gateway.user.incoming.commission.settings"]
        user_rule_model = self.env["pf.gateway.user.incoming.commission.distribution.rule"]
        user_settings = user_settings_model.search(
            [("gateway_user_id", "=", user.id), ("app_name", "=", self.app_name)],
            limit=1,
        )
        settings_values = {
            "gateway_user_id": user.id,
            "app_name": self.app_name,
            "total_percentage": default_settings.default_percentage,
            "settlement_bank_account_id": settlement_account.id,
            "is_active": default_settings.is_active,
        }
        if user_settings:
            user_settings.with_context(skip_gateway_push=True).write(settings_values)
        else:
            user_settings = user_settings_model.with_context(skip_gateway_push=True).create(settings_values)

        user_settings.distribution_rule_ids.with_context(skip_gateway_push=True).unlink()
        created_rules = user_rule_model.browse()
        for default_rule in default_settings.distribution_rule_ids.filtered("is_active"):
            destination_account = self._resolve_bank_account(
                account=default_rule.destination_bank_account_id,
                external_id=default_rule.destination_bank_account_external_id,
                cvu_cbu=default_rule.destination_cvu_cbu,
                label=default_rule.name or _("una regla de distribucion"),
            )
            created_rules |= user_rule_model.with_context(skip_gateway_push=True).create(
                {
                    "settings_id": user_settings.id,
                    "destination_bank_account_id": destination_account.id,
                    "name": default_rule.name,
                    "commission_percentage": default_rule.commission_percentage,
                    "is_active": default_rule.is_active,
                }
            )

        user.with_context(skip_gateway_user_push=True).write(
            {"incoming_commission_setting_selected_id": user_settings.id}
        )
        user_settings._push_to_gateway(propagate_rules=False)
        user_settings._push_distribution_rules_to_gateway()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Comision entrante cargada"),
                "message": _(
                    "Se cargo la configuracion por defecto de %(app)s y %(rules)s regla(s) de distribucion."
                )
                % {"app": self.app_name, "rules": len(created_rules)},
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }
