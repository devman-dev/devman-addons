import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
CHECK_TYPES = ["new_third_party_checks", "check_printing"]


class L10nLatamPaymentMassTransfer(models.TransientModel):
    _inherit = "l10n_latam.payment.mass.transfer"

    operation = fields.Selection(
        [
            ("holding", "Recibido"),
            ("deposited", "Depositado"),
            ("selled", "Vendido"),
            ("delivered", "Entregado"),
            ("transfered", "Transferido"),
            ("handed", "En mano"),
            ("withdrawed", "Retirado"),
            ("reclaimed", "Reclamado"),
            ("rejected", "Rechazado"),
            ("debited", "Debitado"),
            ("returned", "Devuelto"),
            ("changed", "Cambiado"),
            ("used", "Usado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado del cheque",
        required=True,
    )

    total_amount_of_selected_checks = fields.Float(
        string="Importe",
        compute="_compute_total_amount",
        readonly=True,
    )

    destination_journal_id = fields.Many2one(
        comodel_name="account.journal",
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id), ('id', '!=', journal_id)]",
        string="Diario destino",
        required=True,
    )

    destination_journal_bank_id = fields.Many2one(
        comodel_name="account.journal",
        domain="[('type', '=', 'bank'), ('company_id', '=', company_id), ('id', '!=', journal_id)]",
        string="Diario destino",
        readonly=False,
    )

    @api.model
    def default_get(self, fields_list):
        res = super(models.TransientModel, self).default_get(fields_list)

        if "check_ids" in fields_list and "check_ids" not in res:
            if self._context.get("active_model") != "account.payment":
                raise UserError(
                    _(
                        "The register payment wizard should only be called on account.payment records."
                    )
                )
            checks = self.env["account.payment"].browse(
                self._context.get("active_ids", [])
            )
            if checks.filtered(
                lambda x: x.payment_method_line_id.code not in CHECK_TYPES
            ):
                raise "You have select some payments that are not checks. Please call this action from either Own Checks or Thrid Party Checks menues"
            elif not all(check.state == "posted" for check in checks):
                raise UserError(_("All the selected checks must be posted"))

            res["check_ids"] = checks.ids
        return res

    @api.onchange("destination_journal_bank_id")
    def _onchange_destination_journal(self):
        self.destination_journal_id = self.destination_journal_bank_id.id

    @api.onchange("operation")
    def _onchange_operation(self):
        self.destination_journal_id = False
        self.destination_journal_bank_id = False

    def validation_of_check_operation(self, checks_ids):
        for check in checks_ids:
            if check.operation != "handed":
                raise ValidationError(
                    'Para operar los cheques deben estar en estado "En mano"'
                )

    @api.depends("check_ids")
    def _compute_total_amount(self):
        for wizard in self:
            self.validation_of_check_operation(wizard.check_ids)
            total = sum(
                payment.amount_company_currency_signed for payment in wizard.check_ids
            )
            wizard.total_amount_of_selected_checks = total

    @api.depends("check_ids")
    def _compute_journal_company(self):
        # use ._origin because if not a NewId for the checks is used and the returned
        # value for l10n_latam_check_current_journal_id is wrong
        journal = self.check_ids._origin.mapped("l10n_latam_check_current_journal_id")
        payment_method_lines = (
            journal.inbound_payment_method_line_ids
            + journal.outbound_payment_method_line_ids
        )

        if len(journal) != 1 or not payment_method_lines.filtered(
            lambda x: x.code in ["in_third_party_checks", "check_printing"]
        ):
            raise UserError(
                _("All selected checks must be on the same journal and on hand")
            )
        self.journal_id = journal
        self.company_id = journal.company_id.id

    def _create_payments(self):
        self.ensure_one()

        checks = self.check_ids.filtered(
            lambda x: x.payment_method_line_id.code in CHECK_TYPES
        )
        payment_vals_list = []

        payment_method_lines = self.journal_id._get_available_payment_method_lines(
            "outbound"
        )
        pay_method_line = self.env["account.payment.method.line"]

        if all(
            check.payment_type == "outbound" and not check.is_internal_transfer
            for check in checks
        ):
            pay_method_line = payment_method_lines.filtered(
                lambda x: x.code == "check_printing"
            )
        elif all(check.payment_type == "inbound" for check in checks):
            pay_method_line = payment_method_lines.filtered(
                lambda x: x.code == "out_third_party_checks"
            )

        for check in checks:
            payment_vals = {
                "date": self.payment_date,
                "l10n_latam_check_id": check.id,
                "amount": check.amount,
                "payment_type": "outbound",
                "ref": self.communication,
                "journal_id": self.journal_id.id,
                "currency_id": check.currency_id.id,
                "operation": self.operation,
            }
            if self.operation in ("deposited", "selled", "transfered"):
                payment_vals.update(
                    {
                        "is_internal_transfer": True,
                        "payment_method_line_id": pay_method_line.id,
                        "destination_journal_id": self.destination_journal_bank_id.id
                        if self.operation == "deposited"
                        else self.destination_journal_id.id,
                    }
                )
            if check.payment_type == "outbound" and not check.is_internal_transfer:
                payment_vals.update(
                    {
                        "category_check": check.category_check,
                        "checkbook_id": check.checkbook_id.id,
                        "checkbook_type": check.checkbook_type,
                        "endosable": check.endosable,
                        "l10n_latam_check_payment_date": fields.Date.context_today(
                            self
                        ),
                    }
                )
            payment_vals_list.append(payment_vals)

        payments = self.env["account.payment"].create(payment_vals_list)
        payments.action_post()
        return payments
