import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CHECK_TYPES = [
    "new_third_party_checks",
    "in_third_party_checks",
    "out_third_party_checks",
]
_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    l10n_latam_check_payment_date = fields.Date(
        compute="_compute_l10n_latam_check_payment_date",
        readonly=False,
        store=True,
    )
    check_number = fields.Char(
        copy=False,
        readonly=False,
        help="The selected journal is configured to print check numbers. If your pre-printed check paper already has numbers "
        "or if the current numbering is wrong, you can change it in the journal configuration page.",
    )
    checkbook_id = fields.Many2one("account.checkbook", string="Chequera")
    checkbook_type = fields.Selection(
        selection=[("physical", "Fisico"), ("electronic", "Electronico")],
        string="Tipo de cheque",
        store=True,
        default=False,
    )
    endosable = fields.Boolean("Endosable", default=True)
    display_checkbook_type = fields.Boolean(
        compute="_compute_display_checkbook_type", store=True
    )
    display_check_number = fields.Boolean(compute="_compute_display_check_number")
    alpha_check_number = fields.Char(
        compute="_compute_alpha_check_number",
        copy=False,
        store=True,
    )
    category_check = fields.Selection(
        selection=[("common", "Común"), ("deferred", "Diferido")],
        default=False,
        string="Cat.",
    )
    check_issue_date = fields.Date(string="Fecha de emisión")
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
        string="Estado cheque",
        tracking=True,
    )

    @api.depends("category_check")
    def _compute_l10n_latam_check_payment_date(self):
        for payment in self:
            if payment.category_check == "common" and payment.date:
                payment.l10n_latam_check_payment_date = payment.date

    @api.depends("payment_method_code")
    def _compute_display_checkbook_type(self):
        for rec in self:
            rec.display_checkbook_type = (
                rec.payment_type == "inbound"
                and rec.payment_method_code == "new_third_party_checks"
            ) or (
                rec.state == "draft"
                and rec.payment_method_code
                in ["check_printing", "existing_third_party_checks"]
            )

    @api.depends("state", "checkbook_id")
    def _compute_display_check_number(self):
        for rec in self:
            rec.display_check_number = rec.state == "posted" and bool(rec.checkbook_id)

    @api.depends("check_number")
    def _compute_alpha_check_number(self):
        for payment in self:
            if payment.check_number:
                checkbook_name = payment.checkbook_id.name or ""
                payment.alpha_check_number = (
                    f"{checkbook_name} - {payment.check_number}"
                )

    @api.depends("journal_id", "payment_method_code", "checkbook_id")
    def _compute_check_number(self):
        if not self.env.company.ignore_journal_checkbook_sequence:
            return super()._compute_check_number()

        for payment in self:
            if payment.payment_method_code == "manual":
                payment.checkbook_id = False
                payment.check_number = False
                continue

            if payment.payment_method_code == "check_printing" and payment.checkbook_id:
                checkbook = payment.checkbook_id
                next_check = checkbook.get_next_check()
                payment.check_number = str(next_check)
                if checkbook.get_check_number(payment.check_number):
                    raise ValidationError(
                        _(
                            "El número de cheque %s ya está en uso.",
                            payment.check_number,
                        )
                    )
            # No modificar check_number para new_third_party_checks si ya tiene valor
            elif (
                payment.payment_method_code == "new_third_party_checks"
                and not payment.check_number
            ):
                payment.check_number = payment.l10n_latam_check_number or False

    @api.onchange("check_number", "l10n_latam_check_number")
    def _onchange_check_numbers(self):
        if self.payment_method_code == "new_third_party_checks":
            if self.check_number and self.check_number != self.l10n_latam_check_number:
                self.l10n_latam_check_number = self.check_number
            elif (
                self.l10n_latam_check_number
                and self.l10n_latam_check_number != self.check_number
            ):
                self.check_number = self.l10n_latam_check_number

    @api.model
    def get_groupped_by_checkbook(self):
        group_payments = defaultdict(lambda: self.env["account.payment"])
        for payment in self:
            if payment.check_number:
                group_payments[payment.checkbook_id.id] |= payment
        return group_payments

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("amount", 0.0) <= 0.0:
                raise ValidationError(_("El monto del pago debe ser mayor a cero"))

            if (
                vals.get("payment_type") == "outbound"
                and "endosable" in vals
                and not vals["endosable"]
            ):
                raise ValidationError(_("No se puede pagar con un cheque no endosable"))

            if vals.get("category_check") == "common":
                vals["check_issue_date"] = vals.get("l10n_latam_check_payment_date")

            # Sincronizar check_number y l10n_latam_check_number para new_third_party_checks
            if vals.get("payment_method_code") == "new_third_party_checks":
                check_number = vals.get("check_number") or vals.get(
                    "l10n_latam_check_number"
                )
                if check_number:
                    vals["check_number"] = check_number
                    vals[
                        "l10n_latam_check_number"
                    ] = check_number  # Por si acaso el formulario envía solo uno

        payments = super().create(vals_list)
        return payments

    def action_cancel(self):
        res = super().action_cancel()
        for payment in self:
            if payment.state == "cancel":
                if payment.l10n_latam_check_id:
                    payment.l10n_latam_check_id.operation = "cancel"
                    payment.operation = "cancel"
                elif (
                    payment.payment_type == "outbound"
                    and payment.partner_type == "supplier"
                ):
                    payment.operation = "cancel"
        return res

    def action_draft(self):
        res = super().action_draft()
        for payment in self:
            if payment.state == "draft":
                if (
                    payment.payment_type == "inbound"
                    and payment.partner_type == "customer"
                ):
                    if (
                        payment.l10n_latam_check_id
                        and payment.l10n_latam_check_id.operation
                        not in [False, "cancel"]
                    ):
                        raise ValidationError(
                            _(
                                "No se puede volver a borrador un cheque que ya se operó. Cancele las operaciones primero."
                            )
                        )
                    payment.operation = ""
                elif (
                    payment.payment_type == "outbound"
                    and payment.partner_type == "supplier"
                ):
                    if payment.l10n_latam_check_id:
                        payment.l10n_latam_check_id.operation = "handed"
        return res

    def action_post(self):
        res = super().action_post()
        for rec in self:
            if rec.state == "posted":
                if rec.payment_type == "outbound":
                    if rec.l10n_latam_check_id:
                        rec.l10n_latam_check_id.operation = "used"
                        rec.operation = "handed"
                        if (
                            rec.l10n_latam_check_id.alpha_check_number
                            and "-" in rec.l10n_latam_check_id.alpha_check_number
                        ):
                            rec.alpha_check_number = (
                                rec.l10n_latam_check_id.alpha_check_number.split(" - ")[
                                    1
                                ]
                            )
                        else:
                            rec.alpha_check_number = (
                                rec.l10n_latam_check_id.alpha_check_number
                            )
                        rec.l10n_latam_check_bank_id = (
                            rec.l10n_latam_check_id.l10n_latam_check_bank_id
                        )

                    if rec.check_number and rec.payment_method_code not in CHECK_TYPES:
                        if not rec.checkbook_id:
                            raise ValidationError(
                                _("Por favor seleccione una chequera")
                            )
                        if rec.checkbook_id.checks_cancelled:
                            raise ValidationError(
                                _(
                                    "Hay cheques anulados y el siguiente número de la chequera no se modificó"
                                )
                            )
                        checkbook = rec.checkbook_id
                        sequence = int(checkbook.get_next_check())
                        rec.check_number = str(
                            max(int(rec.check_number or 0), sequence)
                        )
                        if int(rec.check_number) > checkbook.next_number:
                            checkbook.next_number = int(rec.check_number)

                elif rec.payment_type == "inbound" and rec.partner_type == "customer":
                    rec.operation = "handed"
                if rec.category_check == "common" and rec.l10n_latam_check_payment_date:
                    rec.check_issue_date = rec.l10n_latam_check_payment_date
        return res

    @api.depends("move_id.name")
    def name_get(self):
        name_payments = []
        for payment in self:
            if payment.payment_method_code in [
                "check_printing",
                "new_third_party_checks",
            ]:
                payment_date = (
                    payment.l10n_latam_check_payment_date.strftime("%d/%m/%Y")
                    if payment.l10n_latam_check_payment_date
                    else ""
                )
                check_number = payment.check_number or ""
                amount = payment.amount_signed  # Compatible con Odoo estándar
                currency_symbol = payment.currency_id.symbol
                name_payments.append(
                    (
                        payment.id,
                        f"(Nro: {check_number}) - {currency_symbol} {amount} - {payment_date}",
                    )
                )
            else:
                name_payments.append(
                    (
                        payment.id,
                        payment.move_id.name
                        if payment.move_id.name != "/"
                        else _("Draft Payment"),
                    )
                )
        return name_payments

    @api.depends("journal_id", "payment_type", "payment_method_line_id")
    def _compute_outstanding_account_id(self):
        check_payments = self.filtered(lambda p: p.payment_method_code in CHECK_TYPES)
        for payment in check_payments:
            account_id = (
                payment.payment_method_line_id.payment_account_id
                or payment.journal_id.suspense_account_id
            )
            if account_id:
                payment.outstanding_account_id = account_id
        super(AccountPayment, self - check_payments)._compute_outstanding_account_id()

    @api.depends("l10n_latam_check_id.operation", "payment_method_line_id.code")
    def _compute_l10n_latam_check_current_journal(self):
        own_checks = self.filtered(
            lambda x: x.payment_method_line_id.code == "check_printing"
        )
        super(
            AccountPayment, self - own_checks
        )._compute_l10n_latam_check_current_journal()
        for rec in own_checks:
            if (
                rec.l10n_latam_check_id
                and rec.l10n_latam_check_id.operation == "handed"
            ):
                rec.l10n_latam_check_current_journal_id = rec.journal_id
            else:
                rec.l10n_latam_check_current_journal_id = False
