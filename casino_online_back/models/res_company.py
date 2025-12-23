# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Configuración de límites de apuesta
    bet_msg_daily   = fields.Char(string="Mensaje límite diario",   default="")
    bet_msg_weekly  = fields.Char(string="Mensaje límite semanal",  default="")
    bet_msg_monthly = fields.Char(string="Mensaje límite mensual",  default="")

    # Configuración de diarios bancarios para casino
    casino_custodia_journal_id = fields.Many2one(
        'account.journal',
        string='Cuenta Bancaria de Custodia',
        help='Diario contable utilizado para registrar los depósitos y ganancias de los usuarios del casino'
    )
    
    casino_operativa_journal_id = fields.Many2one(
        'account.journal',
        string='Cuenta Bancaria Operativa',
        help='Diario contable utilizado para registrar las transferencias de apuestas/pérdidas del casino'
    )

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

        if operation not in ('in', 'out', 'out_final', 'out_withdrawals'):
            raise UserError(_("El parámetro 'operation' debe ser 'in', 'out', 'out_final' o 'out_withdrawals'."))

        if not company.casino_custodia_journal_id:
            _logger.error("No está configurado el diario 'Custodia' en la compañía %s.", company.name)
        #     raise UserError(_("Configure el diario 'casino_deposit_journal_id' en la compañía."))

        if not company.casino_operativa_journal_id:
            _logger.error("No está configurado el diario 'Operativa' en la compañía %s.", company.name)
        #     raise UserError(_("Configure el diario 'casino_bet_transfer_journal_id' en la compañía."))
        
        deposit_custodia = company.casino_custodia_journal_id  #6 #company.casino_deposit_journal_id
        deposit_operativa = company.casino_operativa_journal_id #7 #company.casino_bet_transfer_journal_id

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
        # ENTRADA: transferencia interna al diario de depósitos
        # --------------------------------------------------
        if operation == 'in':
            # Para transferencias internas no se necesita método de pago específico
            vals = {
                'payment_type': 'inbound',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': company.currency_id.id,  # Moneda de la compañía
                'journal_id': deposit_custodia.id,  # Entra en diario custodia
                'destination_journal_id': deposit_operativa.id,  # Resta del diario operativa
                'payment_reference': memo or label,
                'is_reconciled': True,
                'is_internal_transfer': True,
            }
            payment = Payment.create(vals)
            payment.action_post()
            # Agregar memo al asiento contable
            if payment.move_id and memo:
                payment.move_id.narration = memo
            payments |= payment

            if partner_id:
                partner = self.env['res.partner'].browse(partner_id)
                partner.balance_game += amount

        # --------------------------------------------------
        # SALIDA: transferencia interna desde depósitos a operativo
        # --------------------------------------------------
        elif operation in 'out':
            # Transferencia interna por apuesta tipo running
            vals = {
                'payment_type': 'outbound',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': company.currency_id.id,  # Moneda de la compañía
                'journal_id': deposit_operativa.id,  # Entra el monto apostado en el diario operativa
                'destination_journal_id': deposit_custodia.id,  # Se retira del diario custodia
                'payment_reference': memo or label,
                'is_reconciled': True,
                'is_internal_transfer': True
            }
            payment = Payment.create(vals)
            payment.action_post()
            if payment.move_id and memo:
                payment.move_id.narration = memo
            payments |= payment

        # --------------------------------------------------
        # SALIDA PARA RETIROS: pago outbound a cliente
        # --------------------------------------------------
        elif operation == 'out_withdrawals':
            # Retiro: pago outbound desde diario de depósitos al cliente
            transfer_method_out = _get_payment_method(deposit_custodia, 'outbound')

            transfer_out_vals = {
                'payment_type': 'outbound',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id':company.currency_id.id,
                'journal_id': deposit_custodia.id,
                'payment_method_line_id': transfer_method_out.id,
                'payment_reference': memo or label,
                'is_reconciled': True,
                'is_internal_transfer': True,
            }
            transfer_out_payment = Payment.create(transfer_out_vals)
            transfer_out_payment.action_post()
            if transfer_out_payment.move_id and memo:
                transfer_out_payment.move_id.narration = memo
            payments |= transfer_out_payment

        # --------------------------------------------------
        # SALIDA FINAL: pago outbound desde operativo
        # --------------------------------------------------
        elif operation == 'out_final':
            # Salida final: pago outbound desde diario operativo
            transfer_method_out = _get_payment_method(deposit_operativa, 'outbound')

            transfer_out_vals = {
                'payment_type': 'outbound',
                'partner_type': 'customer',
                'partner_id': partner_id or False,
                'amount': amount,
                'date': date,
                'currency_id': company.currency_id.id,
                'journal_id': deposit_operativa.id,  # Entra el monto apostado en el diario operativa
                'destination_journal_id': deposit_custodia.id,  # Se retira del diario custodia
                'payment_reference': memo or label,
                # 'is_reconciled': True,
                'is_internal_transfer': True,
            }
            transfer_out_payment = Payment.create(transfer_out_vals)
            transfer_out_payment.action_post()
            if transfer_out_payment.move_id and memo:
                transfer_out_payment.move_id.narration = memo
            payments |= transfer_out_payment
            
        return payments
