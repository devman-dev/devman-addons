import logging

from odoo import _, fields, models
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class PfGatewayBankAccountAssignmentCreateSubaccountWizard(models.TransientModel):
    _name = "pf.gateway.bank.account.assignment.subaccount.wizard"
    _description = "Crear subcuenta bancaria para asignación de comisionista"

    assignment_id = fields.Many2one(
        "pf.gateway.bank.account.assignment",
        string="Asignación",
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
        if not self.assignment_id:
            raise UserError(_("La asignación no está especificada."))
        if not self.assignment_id.company_id:
            raise UserError(_("La empresa de la asignación no está especificada."))
        if not self.assignment_id.company_id.created_by_user_id:
            raise UserError(_("La empresa no tiene un usuario de gateway asociado."))
        if not self.assignment_id.company_id.created_by_user_id.external_id:
            raise UserError(_("El usuario de gateway de la empresa no tiene ID externo."))
        if not self.app:
            raise UserError(_("La app no está especificada."))

        company_user = self.assignment_id.company_id.created_by_user_id
        _logger.info(
            "[AssignmentCreateSubaccount] Creating subaccount for assignment_id=%s company_user_external_id=%s app=%s",
            self.assignment_id.id,
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
            response = self.assignment_id._gateway_request_json(
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
                company_user = self.assignment_id.company_id.created_by_user_id
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
                    "raw_payload": self.assignment_id._payload_to_text(response),
                }
                bank_account = self.env["pf.gateway.bank.account"].create(bank_account_vals)

            self.assignment_id.write({"bank_account_id": bank_account.id})
            self.created_bank_account_id = bank_account.id

            return {
                "type": "ir.actions.act_window",
                "res_model": "pf.gateway.bank.account.assignment.subaccount.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
            }

        except Exception as exc:
            _logger.exception(
                "[AssignmentCreateSubaccount] Error creating subaccount for assignment_id=%s",
                self.assignment_id.id,
            )
            raise UserError(_("Error al crear la cuenta bancaria: %s") % str(exc))
