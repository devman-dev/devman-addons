import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayUserCreateSubaccountWizard(models.TransientModel):
    _name = "pf.gateway.user.create.subaccount.wizard"
    _description = "Crear subcuenta bancaria (CVU) para usuario"

    user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario Gateway",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    app = fields.Selection(
        [
            ("pagoflex", "PagoFlex"),
            ("sivep", "SIVEP"),
        ],
        string="App",
        required=True,
        default="pagoflex",
        help="Aplicación para la cual se creará la cuenta.",
    )
    existing_cvus_summary = fields.Html(
        string="Resumen de CVUs actuales",
        compute="_compute_existing_cvus_summary",
    )
    created_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta creada",
        readonly=True,
        help="Cuenta bancaria creada en el gateway.",
    )

    @api.depends("user_id")
    def _compute_existing_cvus_summary(self):
        for record in self:
            if not record.user_id:
                record.existing_cvus_summary = ""
                continue
            
            accounts = self.env["pf.gateway.bank.account"].search([
                ("gateway_user_id", "=", record.user_id.id)
            ])
            
            if not accounts:
                record.existing_cvus_summary = _("<p>El usuario no tiene CVUs creados actualmente.</p>")
                continue
            
            summary = "<ul>"
            for acc in accounts:
                status_dict = dict(acc._fields['status'].selection)
                status_label = status_dict.get(acc.status, str(acc.status))
                app_label = acc.app or 'N/A'
                cvu_text = acc.cvu_cbu or "Sin CVU asignado"
                summary += f"<li><b>{cvu_text}</b> - App: {app_label} - Estado: {status_label}</li>"
            summary += "</ul>"
            
            record.existing_cvus_summary = _("<p>El usuario ya posee <b>%s</b> cuenta(s):</p>%s") % (len(accounts), summary)

    def action_create_subaccount(self):
        self.ensure_one()
        if not self.user_id:
            raise UserError(_("El usuario de gateway no está especificado."))
        if not self.user_id.external_id:
            raise UserError(_("El usuario de gateway no tiene ID externo."))
        if not self.app:
            raise UserError(_("La app no está especificada."))

        _logger.info(
            "[UserCreateSubaccount] Creating subaccount for user_external_id=%s app=%s",
            self.user_id.external_id,
            self.app,
        )

        payload = {
            "user_id": self.user_id.external_id,
            "app": self.app,
            "tipo": "psp",
            "return_existing": False,
        }

        try:
            response = self.user_id._gateway_request_json(
                "POST",
                "/admin/gateway/sub-account",
                payload=payload,
            )

            if not isinstance(response, dict):
                raise UserError(_("El gateway devolvió una respuesta inválida al crear la cuenta."))

            bank_account_external_id = response.get("id")
            if not bank_account_external_id:
                raise UserError(_("El gateway no devolvió un ID de cuenta."))

            bank_account = self.env["pf.gateway.bank.account"].search(
                [("external_id", "=", str(bank_account_external_id))],
                limit=1,
            )

            if not bank_account:
                bank_account_vals = {
                    "external_id": str(bank_account_external_id),
                    "origin_id": response.get("origin_id"),
                    "gateway_user_id": self.user_id.id,
                    "cvu_cbu": response.get("cvu_cbu"),
                    "account_type": response.get("account_type"),
                    "alias": response.get("alias"),
                    "status": response.get("status"),
                    "bdc_account_id": response.get("bdc_account_id"),
                    "app": response.get("app"),
                    "currency": response.get("currency"),
                    "active": response.get("status") in ("active", "activated"),
                    "source_created_at": fields.Datetime.now(),
                    "source_updated_at": fields.Datetime.now(),
                    "last_sync_at": fields.Datetime.now(),
                    "raw_payload": self.user_id._payload_to_text(response),
                }
                bank_account = self.env["pf.gateway.bank.account"].create(bank_account_vals)

            self.created_bank_account_id = bank_account.id

            return {
                "type": "ir.actions.act_window",
                "res_model": "pf.gateway.user.create.subaccount.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except Exception as exc:
            _logger.exception(
                "[UserCreateSubaccount] Error creating subaccount for user_id=%s",
                self.user_id.id,
            )
            raise UserError(_("Error al crear la cuenta bancaria: %s") % str(exc))
