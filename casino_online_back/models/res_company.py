# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Configuración de límites de apuesta
    bet_msg_daily   = fields.Char(string="Mensaje límite diario",   default="")
    bet_msg_weekly  = fields.Char(string="Mensaje límite semanal",  default="")
    bet_msg_monthly = fields.Char(string="Mensaje límite mensual",  default="")

    # Configuración de diarios bancarios para casino
    casino_deposit_journal_id = fields.Many2one(
        'account.journal',
        string='Cuenta Bancaria de Custodia',
        help='Diario contable utilizado para registrar los depósitos de los usuarios del casino',
        domain=[('type', 'in', ['bank', 'cash'])]
    )
    
    casino_bet_transfer_journal_id = fields.Many2one(
        'account.journal',
        string='Cuaenta Bancaria Operativa',
        help='Diario contable utilizado para registrar las transferencias de apuestas/pérdidas del casino',
        domain=[('type', 'in', ['bank', 'cash'])]
    )
    
    # Configuración de cuentas contables para casino
    casino_deposit_account_id = fields.Many2one(
        'account.account',
        string='Cuenta para Depósitos de Casino',
        help='Cuenta contable específica para depósitos de casino. Si no se especifica, se usará la cuenta por defecto del diario.',
        domain=[('deprecated', '=', False)]
    )
    
    casino_bet_account_id = fields.Many2one(
        'account.account',
        string='Cuenta para Apuestas de Casino',
        help='Cuenta contable específica para apuestas/pérdidas de casino. Si no se especifica, se usará la cuenta por defecto del diario.',
        domain=[('deprecated', '=', False)]
    )

    def action_casino_register_cash_movement(
        self,
        amount,
        operation,
        partner_id=False,
        date=False,
        label=False,
        memo=False
    ):
        """
        Registra entrada o salida de dinero usando los diarios configurados en la compañía.

        :param amount: Importe positivo del movimiento.
        :param operation: 'in' para entrada, 'out' para salida.
        :param partner_id: (opcional) ID de res.partner asociado al movimiento.
        :param date: (opcional) fecha del movimiento (fields.Date), si no se pasa se usa hoy.
        :param label: (opcional) referencia / concepto del movimiento.
        :return: recordset de account.payment creados.
        """

        self.ensure_one()
        company = self

        if amount <= 0:
            raise UserError(_("El monto debe ser estrictamente positivo."))

        if operation not in ('in', 'out', 'out_final'):
            raise UserError(_("El parámetro 'operation' debe ser 'in', 'out' o 'out_final'."))

        if not company.casino_deposit_journal_id:
            raise UserError(_("Configure el diario 'casino_deposit_journal_id' en la compañía."))

        if not company.casino_bet_transfer_journal_id:
            raise UserError(_("Configure el diario 'casino_bet_transfer_journal_id' en la compañía."))

        deposit_journal = company.casino_deposit_journal_id
        bet_transfer_journal = company.casino_bet_transfer_journal_id

        date = date or fields.Date.context_today(self)
        label = label or (operation == 'in' and _("Entrada de dinero") or _("Salida de dinero"))

        Payment = self.env['account.payment'].sudo()
        payments = Payment.browse()

        # Helper para obtener método de pago
        def _get_payment_method(journal, direction):
            """
            direction: 'inbound', 'outbound'
            """
            if direction == 'inbound':
                method = journal.inbound_payment_method_line_ids[:1]
            else:
                method = journal.outbound_payment_method_line_ids[:1]
            if not method:
                raise UserError(_(
                    "El diario '%s' no tiene ningún método de pago %s configurado."
                ) % (journal.display_name, direction))
            return method

        # --------------------------------------------------
        # ENTRADA: un solo pago inbound al diario de depósitos
        # --------------------------------------------------
        if operation == 'in':
            method_line = _get_payment_method(deposit_journal, 'inbound')

            vals = {
                'payment_type': 'inbound',
                'partner_type': partner_id and 'customer' or 'customer',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': deposit_journal.currency_id.id or company.currency_id.id,
                'journal_id': deposit_journal.id,
                'payment_method_line_id': method_line.id,
                'memo': memo or label,
            }
            payment = Payment.create(vals)
            payment.action_post()
            # Agregar memo al asiento contable
            if payment.move_id and memo:
                payment.move_id.narration = memo
            payments |= payment

        # --------------------------------------------------
        # SALIDA:
        # 1) salida desde depósito (outbound)
        # 2) ingreso en operativo (inbound)
        # --------------------------------------------------
        elif operation in 'out':
            # Paso 1: salida desde diario de depósito
            transfer_method_out = _get_payment_method(deposit_journal, 'outbound')

            transfer_out_vals = {
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': deposit_journal.currency_id.id or company.currency_id.id,
                'journal_id': deposit_journal.id,
                'payment_method_line_id': transfer_method_out.id,
                'memo': memo or label,
            }
            transfer_out_payment = Payment.create(transfer_out_vals)
            transfer_out_payment.action_post()
            if transfer_out_payment.move_id and memo:
                transfer_out_payment.move_id.narration = memo
            payments |= transfer_out_payment

            # Paso 2: entrada al diario operativo
            transfer_method_in = _get_payment_method(bet_transfer_journal, 'inbound')

            transfer_in_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': bet_transfer_journal.currency_id.id or company.currency_id.id,
                'journal_id': bet_transfer_journal.id,
                'payment_method_line_id': transfer_method_in.id,
                'memo': memo or label,
            }
            transfer_in_payment = Payment.create(transfer_in_vals)
            transfer_in_payment.action_post()
            if transfer_in_payment.move_id and memo:
                transfer_in_payment.move_id.narration = memo
            payments |= transfer_in_payment
        elif operation == 'out_final':
            # Paso único: salida desde diario operativo
            transfer_method_out = _get_payment_method(bet_transfer_journal, 'outbound')

            transfer_out_vals = {
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': bet_transfer_journal.currency_id.id or company.currency_id.id,
                'journal_id': bet_transfer_journal.id,
                'payment_method_line_id': transfer_method_out.id,
                'memo': memo or label,
            }
            transfer_out_payment = Payment.create(transfer_out_vals)
            transfer_out_payment.action_post()
            if transfer_out_payment.move_id and memo:
                transfer_out_payment.move_id.narration = memo
            payments |= transfer_out_payment
            
        return payments
