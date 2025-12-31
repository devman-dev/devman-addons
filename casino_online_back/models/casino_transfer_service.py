from odoo import api, fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class CasinoTransferService(models.AbstractModel):
    _name = "casino.transfer.service"
    _description = "Casino Transfer Service"

    @api.model
    def create_internal_transfer_payment(
        self, *, journal_src, journal_dst, amount, date=None, currency=None, memo=None, partner=None, casino_operation_type=None
    ):
        date = date or fields.Date.context_today(self)
        company = self.env.company
        currency = currency or company.currency_id

        Payment = self.env["account.payment"].with_company(company)

        vals = {
            "payment_type": "outbound",
            "partner_id": partner.id if partner else False,
            "amount": amount,
            "date": date,
            "currency_id": currency.id,
            "journal_id": journal_src.id,
            "destination_journal_id": journal_dst.id,
            "is_internal_transfer": True,
            "payment_reference": memo or _("Internal Transfer"),
        }
        if casino_operation_type:
            vals["casino_operation_type"] = casino_operation_type

        # Solo este contexto: evita tu auto-post si todavía existiera algo residual
        payment = Payment.with_context(skip_auto_post=True).create(vals)

        # En este punto, move_id debería existir o se creará al postear
        payment.action_post()

        if not payment.move_id:
          _logger.error("Internal transfer payment was created without an accounting entry (move_id). Payment ID: %s", payment.id)
          _logger.exception("Internal transfer payment was created without an accounting entry (move_id).")
            # raise UserError(_("Internal transfer payment was created without an accounting entry (move_id)."))

        return payment

    def create_internal_transfer_payment2(
        self,
        *,
        journal_src,
        journal_dst,
        amount,
        date=None,
        currency=None,
        memo=None,
        partner=None,
        casino_operation_type=None,
    ):
        """
        Crea una transferencia interna real (account.payment) para que aparezca en Banco y Caja -> Transferencias.
        Evita writes sobre move posteado: no escribe en move_id, no reconcilia a ciegas.
        """

        date = date or fields.Date.context_today(self)
        company = self.env.company
        currency = currency or company.currency_id

        if amount <= 0:
            raise UserError(_("Amount must be positive."))

        Payment = self.env["account.payment"].with_company(company)

        vals = {
            "payment_type": "outbound",              # Odoo lo usa para transferencias desde origen
            "partner_id": partner.id if partner else False,
            "amount": amount,
            "date": date,
            "currency_id": currency.id,
            "journal_id": journal_src.id,
            "destination_journal_id": journal_dst.id,
            "is_internal_transfer": True,
            "payment_reference": memo or _("Internal Transfer"),
        }
        if casino_operation_type:
            vals["casino_operation_type"] = casino_operation_type

        # Contextos “posibles” (no garantizados) para evitar auto-post/sync en algunos stacks.
        # Si tu core no los usa, no perjudican (solo no ayudan).
        ctx = dict(self.env.context, skip_auto_post=True)
        ctx.update({
            "skip_account_move_synchronization": True,
            "skip_payment_move_sync": True,
            "skip_post": True,
            "no_post": True,
        })

        payment = Payment.with_context(ctx).create(vals)

        # Posteo controlado: sólo si el move aún está draft.
        if payment.move_id and payment.move_id.state == "draft":
            payment.action_post()

        # Validación: debe existir move y debe quedar posted.
        if not payment.move_id:
            _logger.error("Internal transfer payment was created without an accounting entry (move_id). Payment ID: %s", payment.id)
            raise UserError(_("Internal transfer payment was created without an accounting entry (move_id)."))
        if payment.move_id.state != "posted":
            _logger.error("Internal transfer accounting entry is not posted. Payment ID: %s, Move ID: %s, State: %s", payment.id, payment.move_id.id, payment.move_id.state)
            raise UserError(_("Internal transfer accounting entry is not posted. State: %s") % payment.move_id.state)

        # Importante: NO escribir payment.move_id.* después del posteo.
        return payment
