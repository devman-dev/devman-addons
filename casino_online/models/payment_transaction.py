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
                    company = tx.company_id or self.env.company
                    
                    if partner and amount > 0:
                        # Actualizar el balance_game del partner
                        balance = partner.balance_game + amount
                        partner.balance_game = balance
                        partner.flush_recordset()
                        partner.invalidate_recordset(['balance_game'])

                        self.env['bus.bus']._sendone(
                            partner, "casino_wallet_update", {"partner_id": partner.id, "balance": balance}
                        )
                        _logger.info(
                            "PaymentTransaction: Updated balance_game for partner %s (tx %s). "
                            "Added %s. New balance: %s",
                            partner.id, tx.id, amount, partner.balance_game
                        )
                        
                        # Crear account.payment para registro contable
                        # Obtener el diario de custodia configurado en la compañía
                        journal = company.casino_deposit_journal_id or company.casino_custodia_journal_id
                        
                        if not journal:
                            _logger.warning(
                                "PaymentTransaction: No casino journal configured for company %s",
                                company.id
                            )
                        else:
                            # Buscar o crear el payment
                            payment = self.env['account.payment'].sudo().search(
                                [('payment_transaction_id', '=', tx.id)],
                                limit=1
                            )
                            
                            if not payment:
                                # Obtener payment method line (inbound) del journal
                                payment_method_line = journal.inbound_payment_method_line_ids.filtered(
                                    lambda l: l.code in ['manual', 'electronic']
                                )[:1]
                                
                                if not payment_method_line:
                                    payment_method_line = journal.inbound_payment_method_line_ids[:1]
                                
                                if not payment_method_line:
                                    _logger.error(
                                        "PaymentTransaction: No inbound payment method found for journal %s",
                                        journal.id
                                    )
                                else:
                                    # Crear el payment
                                    payment_vals = {
                                        'partner_id': partner.id,
                                        'amount': amount,
                                        'payment_type': 'inbound',
                                        'partner_type': 'customer',
                                        'journal_id': journal.id,
                                        'payment_method_line_id': payment_method_line.id,
                                        # 'date': tx.date or fields.Date.context_today(self),
                                        'memo': tx.reference,
                                        'payment_transaction_id': tx.id,
                                        'casino_operation_type': 'deposit',
                                    }
                                    
                                    try:
                                        payment = self.env['account.payment'].sudo().with_context(
                                            skip_auto_post=True
                                        ).create(payment_vals)
                                        
                                        _logger.info(
                                            "PaymentTransaction: Created payment %s for tx %s",
                                            payment.id, tx.id
                                        )
                                        
                                        # Vincular payment con transaction
                                        tx.payment_id = payment.id
                                        
                                    except Exception as e:
                                        _logger.error(
                                            "PaymentTransaction: Error creating payment for tx %s: %s",
                                            tx.id, e, exc_info=True
                                        )
                            
                            # Postear el payment si está en draft
                            if payment and payment.state == 'draft':
                                try:
                                    payment.action_post()
                                    _logger.info(
                                        "PaymentTransaction: Posted payment %s for tx %s",
                                        payment.id, tx.id
                                    )
                                except Exception as e:
                                    _logger.error(
                                        "PaymentTransaction: Error posting payment %s: %s",
                                        payment.id, e, exc_info=True
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

