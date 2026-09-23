"""casino.money.flow — Servicio centralizado de movimientos monetarios.

ÚNICO punto autorizado para modificar balance_game después de la migración.
"""
import logging
from odoo import models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CasinoMoneyFlow(models.AbstractModel):
    _name = 'casino.money.flow'
    _description = 'Centralized Money Movement Processor'

    # ── Operation Type → Transaction Type Mapping ───────────────────
    _OPERATION_MAP = {
        'deposit':      {'transaction_type': 'deposit',      'direction': 'credit'},
        'withdrawal':   {'transaction_type': 'withdrawal',   'direction': 'debit'},
        'bet':          {'transaction_type': 'bet',          'direction': 'debit'},
        'win':          {'transaction_type': 'win',          'direction': 'credit'},
        'bonus':        {'transaction_type': 'bonus',        'direction': 'credit'},
        'surcharge':    {'transaction_type': 'surcharge',    'direction': 'debit'},
        'adjustment':   {'transaction_type': 'adjustment',   'direction': 'credit'},
        'refund':       {'transaction_type': 'refund',       'direction': 'credit'},
        'transfer_in':  {'transaction_type': 'transfer_in',  'direction': 'credit'},
        'transfer_out': {'transaction_type': 'transfer_out', 'direction': 'debit'},
        'commission':   {'transaction_type': 'commission',   'direction': 'debit'},
        'liquidation':  {'transaction_type': 'liquidation',  'direction': 'debit'},
    }

    # ────────────────────────────────────────────────────────────────
    # process_operation — ÚNICO método autorizado para modificar
    # balance_game y crear wallet transactions.
    # ────────────────────────────────────────────────────────────────
    def process_operation(self, operation_type, partner_id, amount, **kwargs):
        """
        Centralized money movement processor.

        After full migration, this is the ONLY method authorized to:
          - lock a partner row
          - read balance_game for a partner
          - validate funds
          - calculate balance_before / balance_after
          - create casino.wallet.transaction records
          - update balance_game
          - update wallet.balance

        :param operation_type:  key from _OPERATION_MAP
        :param partner_id:      res.partner ID (int) or recordset
        :param amount:          positive float
        :param kwargs:
            idempotency_key     — unique external key for idempotency
            reference           — internal reference (e.g. account.move)
            external_reference  — external reference (e.g. gateway op_id)
            origin_model        — model name that originated this op
            origin_id           — record id that originated this op
            note                — text note
            wallet_type         — 'player' (default), 'agent', 'system'
            wallet_id           — explicit wallet ID (skip find/create)
            direction_override  — override _OPERATION_MAP direction
            reversed_tx_id      — original tx ID being reversed
            performed_by        — res.users recordset (defaults to env.user)
        :return:                casino.wallet.transaction (confirmed)
        """
        # self.ensure_one()  -- removed: AbstractModel cant be singleton

        # ── PASO 1: Validar operación ──────────────────────────────
        op_config = self._OPERATION_MAP.get(operation_type)
        if not op_config:
            raise UserError(
                _("Tipo de operación no soportado: %s") % operation_type
            )
        if amount <= 0:
            raise UserError(_("El monto debe ser estrictamente positivo."))

        transaction_type = op_config['transaction_type']
        direction = kwargs.get('direction_override', op_config['direction'])
        idempotency_key = kwargs.get('idempotency_key')
        wallet_type = kwargs.get('wallet_type', 'player')

        # ── PASO 2: Verificar idempotencia ────────────────────────
        if idempotency_key:
            existing = self.env['casino.wallet.transaction'].sudo().search([
                ('idempotency_key', '=', idempotency_key),
            ], limit=1)
            if existing:
                if existing.state == 'confirmed':
                    _logger.info(
                        "Idempotent replay: returning tx %s for key %s",
                        existing.name, idempotency_key,
                    )
                    return existing
                if existing.state in ('draft', 'pending'):
                    _logger.warning(
                        "Stale tx %s for key %s in state %s",
                        existing.name, idempotency_key, existing.state,
                    )
                    raise UserError(_(
                        'Existe una transacción pendiente (%s) para '
                        'esta operación (%s). Contacte al administrador.'
                    ) % (existing.name, idempotency_key))
                # cancelled or reversed → allow re-processing
                _logger.info(
                    "Found %s tx %s for key %s, will create new",
                    existing.state, existing.name, idempotency_key,
                )

        # Resolve partner recordset
        if isinstance(partner_id, int):
            partner = self.env['res.partner'].browse(partner_id)
        else:
            partner = partner_id
        if not partner.exists():
            raise UserError(_("El partner no existe."))

        # ── PASO 3: SELECT FOR UPDATE sobre res_partner ─────────────
        # This lock is held until the Odoo transaction commits (or rolls back).
        # Any concurrent process_operation() on the same partner will block here.
        self.env.cr.execute(
            "SELECT id FROM res_partner WHERE id = %s FOR UPDATE",
            [partner.id],
        )

        # ── PASO 4: Localizar o crear wallet (seguro bajo lock) ──
        explicit_wallet_id = kwargs.get('wallet_id')
        if explicit_wallet_id:
            wallet = self.env['casino.wallet'].sudo().browse(explicit_wallet_id)
            if not wallet.exists():
                raise UserError(_(
                    "El wallet especificado (id=%s) no existe."
                ) % explicit_wallet_id)
            if wallet.partner_id.id != partner.id:
                raise UserError(_(
                    "El wallet (id=%s) no pertenece al partner (id=%s)."
                ) % (explicit_wallet_id, partner.id))
        else:
            wallet = self._find_or_create_wallet(partner, wallet_type)

        # ── PASO 5: Invalidar cache ORM ────────────────────────────
        partner.invalidate_recordset(['balance_game'])

        # ── PASO 6: Leer balance fresco ────────────────────────────
        balance_before = wallet.balance

        # ── PASO 7: Validar fondos para débitos ────────────────────
        if direction == 'debit' and balance_before < amount:
            raise UserError(_(
                'Saldo insuficiente. Balance: %(balance)s, '
                'Requerido: %(amount)s'
            ) % {'balance': balance_before, 'amount': amount})

        # ── PASO 8: Calcular balance_after ─────────────────────────
        if direction == 'credit':
            balance_after = balance_before + amount
        else:
            balance_after = balance_before - amount

        # ── PASO 9: Crear wallet.transaction en draft ──────────────
        tx_vals = {
            'wallet_id': wallet.id,
            'transaction_type': transaction_type,
            'amount': amount,
            'direction': direction,
            'balance_before': balance_before,
            'balance_after': balance_after,
            'reference': kwargs.get('reference'),
            'external_reference': kwargs.get('external_reference'),
            'origin_model': kwargs.get('origin_model'),
            'origin_id': kwargs.get('origin_id'),
            'note': kwargs.get('note'),
            'idempotency_key': idempotency_key,
            'state': 'draft',
        }
        reversed_tx_id = kwargs.get('reversed_tx_id')
        if reversed_tx_id:
            tx_vals['reversed_tx_id'] = reversed_tx_id
        if kwargs.get('performed_by'):
            tx_vals['performed_by'] = kwargs['performed_by'].id

        transaction = self.env['casino.wallet.transaction'].sudo().create(
            tx_vals
        )

        # ── PASO 10: Validar y confirmar via action_confirm() ──────
        transaction.action_confirm()

        # ── PASO 11: Actualizar balance_game ──────────────────────
        partner.write({'balance_game': balance_after})

        # ── PASO 12: Sincronizar wallet.balance ────────────────────
        wallet.write({'balance': balance_after})

        _logger.info(
            "Money flow: %s %s %s | partner=%s | before=%s after=%s | tx=%s",
            operation_type, direction, amount,
            partner.id, balance_before, balance_after, transaction.name,
        )

        return transaction

    # ────────────────────────────────────────────────────────────────
    # Helper — Find or create wallet
    # ────────────────────────────────────────────────────────────────
    def _find_or_create_wallet(self, partner, wallet_type='player'):
        """Find or create a casino.wallet for partner + type + company."""
        Wallet = self.env['casino.wallet'].sudo()
        company = self.env.company

        wallet = Wallet.search([
            ('partner_id', '=', partner.id),
            ('wallet_type', '=', wallet_type),
            ('company_id', '=', company.id),
        ], limit=1)

        if wallet:
            return wallet

        # Safe under lock — concurrent requests are serialized
        wallet = Wallet.create({
            'partner_id': partner.id,
            'wallet_type': wallet_type,
            'company_id': company.id,
        })
        _logger.info(
            "Auto-created %s wallet for partner %s (id=%s)",
            wallet_type, partner.id, wallet.id,
        )
        return wallet