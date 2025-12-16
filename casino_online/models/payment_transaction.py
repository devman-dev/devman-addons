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
        """
        result = super()._set_done()
        
        for tx in self:
            try:
                # Verificar que sea un depósito de casino (prefix DEP)
                if tx.reference and tx.reference.startswith('DEP'):
                    partner = tx.partner_id
                    amount = tx.amount
                    
                    if partner and amount > 0:
                        # Actualizar el balance_game del partner
                        partner.balance_game += amount
                        _logger.info(
                            "PaymentTransaction: Updated balance_game for partner %s (tx %s). "
                            "Added %s. New balance: %s",
                            partner.id, tx.id, amount, partner.balance_game
                        )
                    else:
                        _logger.warning(
                            "PaymentTransaction: Transaction %s has no partner or invalid amount",
                            tx.id
                        )
            except Exception as e:
                _logger.error(
                    "PaymentTransaction: Error updating balance_game for tx %s: %s",
                    tx.id, e, exc_info=True
                )
                # No fallar la transacción si hay error al actualizar balance
        
        return result
