import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayCompanyLocationCreateSubaccountWizard(models.TransientModel):
    _name = "pf.gateway.company.location.create.subaccount.wizard"
    _description = "Crear subcuenta bancaria para local de empresa"

    location_id = fields.Many2one(
        "pf.gateway.company.location",
        string="Local",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    user_id = fields.Many2one(
        "pf.gateway.user",
        string="Usuario Gateway",
        required=True,
        help="Usuario del gateway para el cual se creará la cuenta.",
    )
    app = fields.Selection(
        [
            ("pagoflex", "PagoFlex"),
            ("sivep", "SIVEP"),
        ],
        string="App",
        required=True,
        help="Aplicación para la cual se creará la cuenta.",
    )
    created_bank_account_id = fields.Many2one(
        "pf.gateway.bank.account",
        string="Cuenta creada",
        readonly=True,
        help="Cuenta bancaria creada en el gateway.",
    )

    def action_create_subaccount(self):
        self.ensure_one()
        if not self.location_id:
            raise UserError(_("El local no está especificado."))
        if not self.location_id.company_id:
            raise UserError(_("La empresa del local no está especificada."))
        if not self.location_id.company_id.created_by_user_id:
            raise UserError(_("La empresa no tiene un usuario de gateway asociado."))
        if not self.location_id.company_id.created_by_user_id.external_id:
            raise UserError(_("El usuario de gateway de la empresa no tiene ID externo."))
        if not self.app:
            raise UserError(_("La app no está especificada."))

        company_user = self.location_id.company_id.created_by_user_id
        _logger.info(
            "[LocationCreateSubaccount] Creating subaccount for location_id=%s company_user_external_id=%s app=%s",
            self.location_id.id,
            company_user.external_id,
            self.app,
        )

        payload = {
            "user_id": company_user.external_id,
            "app": self.app,
            "tipo": "psp",
            "return_existing": False,
        }

        try:
            response = self.location_id._gateway_request_json(
                "POST",
                "/admin/gateway/sub-account",
                payload=payload,
            )

            if not isinstance(response, dict):
                raise UserError(_("El gateway devolvió una respuesta inválida al crear la cuenta."))

            _logger.debug("[LocationCreateSubaccount] Gateway response: %s", response)

            # Buscar o crear la cuenta bancaria localmente
            bank_account_external_id = response.get("id")
            if not bank_account_external_id:
                raise UserError(_("El gateway no devolvió un ID de cuenta."))

            bank_account = self.env["pf.gateway.bank.account"].search(
                [("external_id", "=", str(bank_account_external_id))],
                limit=1,
            )

            if not bank_account:
                # Crear la cuenta bancaria localmente
                company_user = self.location_id.company_id.created_by_user_id
                bank_account_vals = {
                    "external_id": str(bank_account_external_id),
                    "origin_id": response.get("origin_id"),
                    "gateway_user_id": company_user.id,
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
                    "raw_payload": self.location_id._payload_to_text(response),
                }
                bank_account = self.env["pf.gateway.bank.account"].create(bank_account_vals)
                _logger.info(
                    "[LocationCreateSubaccount] Created bank account id=%s external_id=%s",
                    bank_account.id,
                    bank_account.external_id,
                )

            # Asignar la cuenta al local
            self.location_id.write({"bank_account_id": bank_account.id})
            self.created_bank_account_id = bank_account.id

            _logger.info(
                "[LocationCreateSubaccount] Assigned bank account id=%s to location_id=%s",
                bank_account.id,
                self.location_id.id,
            )

            return {
                "type": "ir.actions.act_window",
                "res_model": "pf.gateway.company.location.create.subaccount.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except Exception as exc:
            _logger.exception(
                "[LocationCreateSubaccount] Error creating subaccount for location_id=%s",
                self.location_id.id,
            )
            raise UserError(
                _("Error al crear la cuenta bancaria: %s") % str(exc)
            )
