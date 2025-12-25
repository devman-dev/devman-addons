# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _set_done(self):
        """
        Override del método que cambia el estado a 'done'.
        Actualiza balance_game del partner si es un depósito de casino.
        También crea un account.payment con casino_operation_type='deposit'.
        """
        result = super()._set_done()
        
        for tx in self:
            try:
                # Verificar que sea un depósito de casino (prefix DEP)
                if tx.reference and tx.reference.startswith('DEP'):
                    partner = tx.partner_id
                    amount = tx.amount
                    company = tx.company_id or self.env.company
                    
                    if partner and amount > 0:
                        # Actualizar el balance_game del partner
                        partner.balance_game += amount
                        _logger.info(
                            "PaymentTransaction: Updated balance_game for partner %s (tx %s). "
                            "Added %s. New balance: %s",
                            partner.id, tx.id, amount, partner.balance_game
                        )
                        
                        # Crear el account.payment con casino_operation_type='deposit'
                        Payment = self.env['account.payment'].sudo()

                        method_line_id = self._get_payment_method_line_id(company)
                        if not method_line_id:
                            _logger.warning("PaymentTransaction: No payment_method_line_id available for tx %s", tx.id)
                            continue

                        method_line = self.env['account.payment.method.line'].sudo().browse(method_line_id)

                        payment_vals = {
                            'partner_id': partner.id,
                            'amount': amount,
                            'payment_type': 'inbound',
                            'partner_type': 'customer',
                            'currency_id': tx.currency_id.id,
                            'company_id': company.id,
                            'payment_method_line_id': method_line_id,
                            'memo': tx.reference,
                            'casino_operation_type': 'deposit',
                        }

                        # Journal debe alinearse con el método; si no, usar el diario de la compañía
                        if method_line.journal_id:
                            payment_vals['journal_id'] = method_line.journal_id.id
                        elif company.casino_deposit_journal_id:
                            payment_vals['journal_id'] = company.casino_deposit_journal_id.id

                        payment = Payment.create(payment_vals)
                        _logger.info(
                            "PaymentTransaction: Created account.payment %s for deposit tx %s with casino_operation_type='deposit'",
                            payment.id, tx.id
                        )

                        # Publicar el pago automáticamente
                        if payment.state in ('draft', 'in_process'):
                            payment.action_post()
                            _logger.info("PaymentTransaction: Posted payment %s for tx %s", payment.id, tx.id)
                        
                    else:
                        _logger.warning(
                            "PaymentTransaction: Transaction %s has no partner or invalid amount",
                            tx.id
                        )
            except Exception as e:
                _logger.error(
                    "PaymentTransaction: Error updating balance_game or creating payment for tx %s: %s",
                    tx.id, e, exc_info=True
                )
                # No fallar la transacción si hay error al actualizar balance
        
        return result
    
    def _get_payment_method_line_id(self, company):
        """Obtiene un payment_method_line_id válido para pagos entrantes."""
        PaymentMethodLine = self.env['account.payment.method.line'].sudo()
        
        # Buscar en el journal de casino si existe
        if company.casino_deposit_journal_id:
            line = PaymentMethodLine.search([
                ('journal_id', '=', company.casino_deposit_journal_id.id),
                ('payment_type', '=', 'inbound'),
            ], limit=1)
            if line:
                return line.id
        
        # Fallback: buscar cualquier línea de pago entrante
        line = PaymentMethodLine.search([
            ('company_id', '=', company.id),
            ('payment_type', '=', 'inbound'),
        ], limit=1)
        
        return line.id if line else False
