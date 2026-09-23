"""casino.wallet.transaction — Ledger transaccional inmutable."""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class CasinoWalletTransaction(models.Model):
    _name = 'casino.wallet.transaction'
    _description = 'Casino Wallet Transaction (Ledger)'
    _order = 'id desc'
    _rec_name = 'name'

    # ── Identificación ──────────────────────────────────────────────
    name = fields.Char(
        string='Referencia',
        required=True,
        index=True,
        default='/',
        copy=False,
    )
    wallet_id = fields.Many2one(
        comodel_name='casino.wallet',
        string='Wallet',
        required=True,
        index=True,
        ondelete='restrict',
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        related='wallet_id.partner_id',
        store=True,
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario vinculado',
        compute='_compute_user_id',
        readonly=True,
        store=False,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        related='wallet_id.company_id',
        store=True,
        index=True,
    )

    # ── Operación ───────────────────────────────────────────────────
    transaction_type = fields.Selection(
        selection=[
            ('deposit', 'Depósito'),
            ('withdrawal', 'Retiro'),
            ('bet', 'Apuesta'),
            ('win', 'Premio'),
            ('bonus', 'Bono'),
            ('surcharge', 'Recargo'),
            ('adjustment', 'Ajuste'),
            ('refund', 'Devolución'),
            ('transfer_in', 'Transferencia (entrada)'),
            ('transfer_out', 'Transferencia (salida)'),
            ('commission', 'Comisión'),
            ('liquidation', 'Liquidación'),
        ],
        string='Tipo de Transacción',
        required=True,
        index=True,
    )
    amount = fields.Monetary(
        string='Monto',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        related='wallet_id.currency_id',
        store=True,
    )
    direction = fields.Selection(
        selection=[
            ('credit', 'Crédito'),
            ('debit', 'Débito'),
        ],
        string='Dirección',
        required=True,
        default='credit',
    )
    balance_before = fields.Monetary(
        string='Balance Anterior',
        currency_field='currency_id',
        readonly=True,
    )
    balance_after = fields.Monetary(
        string='Balance Posterior',
        currency_field='currency_id',
        readonly=True,
    )

    # ── Idempotencia ────────────────────────────────────────────────
    idempotency_key = fields.Char(
        string='Clave de Idempotencia',
        index=True,
        copy=False,
        help='Clave externa única que evita procesamiento duplicado. '
             'NULL es válido (múltiples NULLs no colisionan en PostgreSQL).',
    )

    # ── Referencia ───────────────────────────────────────────────────
    reference = fields.Char(
        string='Referencia Interna',
        index=True,
        help='Referencia opcional a documento interno (ej: account.move).',
    )
    external_reference = fields.Char(
        string='Referencia Externa',
        index=True,
        help='ID de transacción enviado por un gateway/proveedor externo.',
    )
    origin_model = fields.Char(
        string='Modelo de Origen',
        help='Modelo técnico que originó esta transacción (ej: casino.game.session).',
    )
    origin_id = fields.Integer(
        string='ID de Origen',
        help='ID del registro que originó esta transacción.',
    )

    # ── Reversión ───────────────────────────────────────────────────
    reversed_tx_id = fields.Many2one(
        comodel_name='casino.wallet.transaction',
        string='Transacción Revertida',
        index=True,
        copy=False,
        ondelete='set null',
        help='Transacción original que fue revertida por esta operación compensatoria.',
    )
    is_reversal = fields.Boolean(
        string='Es Reversión',
        compute='_compute_is_reversal',
        store=True,
        index=True,
    )
    reversal_tx_id = fields.Many2one(
        comodel_name='casino.wallet.transaction',
        string='Reversada por',
        index=True,
        copy=False,
        ondelete='set null',
        help='Transacción compensatoria que revierte esta operación.',
    )

    # ── Auditoría ───────────────────────────────────────────────────
    performed_by = fields.Many2one(
        comodel_name='res.users',
        string='Realizado por',
        default=lambda self: self.env.user,
        index=True,
        readonly=True,
    )
    performed_at = fields.Datetime(
        string='Fecha de ejecución',
        default=fields.Datetime.now,
        readonly=True,
        copy=False,
    )

    # ── Estado ───────────────────────────────────────────────────────
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('pending', 'Pendiente'),
            ('confirmed', 'Confirmada'),
            ('cancelled', 'Cancelada'),
            ('reversed', 'Reversada'),
        ],
        string='Estado',
        default='draft',
        required=True,
        index=True,
        tracking=True,
    )

    # ── Notas y comprobantes ────────────────────────────────────────
    note = fields.Text(string='Nota')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        string='Comprobantes',
    )

    # ── Restricciones SQL ───────────────────────────────────────────
    _sql_constraints = [
        (
            'casino_wallet_tx_amount_positive',
            'CHECK(amount > 0)',
            'El monto de la transacción debe ser mayor a cero.',
        ),
        (
            'casino_wallet_tx_idempotency_key_uniq',
            'UNIQUE(idempotency_key)',
            'Ya existe una transacción con esta clave de idempotencia.',
        ),
        (
            'casino_wallet_tx_reversed_tx_id_uniq',
            'UNIQUE(reversed_tx_id)',
            'Esta transacción ya fue revertida por otra operación.',
        ),
        (
            'casino_wallet_tx_reversal_tx_id_uniq',
            'UNIQUE(reversal_tx_id)',
            'Esta transacción compensatoria ya está enlazada a otra original.',
        ),
    ]

    # ── Restricciones Python ────────────────────────────────────────
    @api.constrains('amount')
    def _check_amount_positive(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('El monto debe ser mayor a cero.'))

    @api.constrains('wallet_id')
    def _check_wallet_exists(self):
        for rec in self:
            if not rec.wallet_id:
                raise ValidationError(_(
                    'La transacción debe estar asociada a un wallet.'
                ))

    @api.constrains('state', 'id')
    def _check_confirmed_immutable(self):
        """Una transacción confirmada NO puede editarse ni eliminarse."""
        for rec in self:
            if rec.state == 'confirmed':
                if rec._origin and rec._origin.state == 'confirmed':
                    protected = {
                        'transaction_type', 'amount', 'direction',
                        'wallet_id', 'balance_before', 'balance_after',
                    }
                    dirty = rec._get_dirty_fields()
                    if any(f in dirty for f in protected):
                        raise ValidationError(_(
                            'No se puede modificar una transacción confirmada. '
                            'Debe crear una transacción de reversión.'
                        ))

    # ── Computed ───────────────────────────────────────────────────
    @api.depends('reversed_tx_id')
    def _compute_is_reversal(self):
        for rec in self:
            rec.is_reversal = bool(rec.reversed_tx_id)

    @api.depends('partner_id.user_ids')
    def _compute_user_id(self):
        for rec in self:
            rec.user_id = (
                rec.partner_id.user_ids[:1].id
                if rec.partner_id.user_ids
                else False
            )

    # ── Métodos de ciclo de vida ────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'casino.wallet.transaction'
                ) or '/'
        return super().create(vals_list)

    def unlink(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_(
                    'No se puede eliminar una transacción confirmada. '
                    'Utilice una transacción de reversión en su lugar.'
                ))
        return super().unlink()

    def write(self, vals):
        """Protege la inmutabilidad del ledger.

        Transacciones confirmadas:
        - Campos financieros (amount, direction, wallet, balances): bloqueados.
        - state: solo permitida transición confirmed → reversed via
          action_reverse(), que es la única ruta controlada.
        - Campos de metadata (note, reference, etc.): permitidos.
        """
        for rec in self:
            if rec.state == 'confirmed':
                new_state = vals.get('state')
                if new_state is not None:
                    # Única transición permitida: confirmed → reversed
                    # y solo junto con reversal_tx_id
                    if (new_state == 'reversed'
                            and set(vals.keys()).issubset(
                                {'state', 'reversal_tx_id'})):
                        continue
                    raise UserError(_(
                        'No se puede cambiar el estado de una transacción '
                        'confirmada (%(tx)s). '
                        'La única transición permitida es '
                        'confirmed → reversed vía action_reverse().'
                    ) % {'tx': rec.name})

                # Campos financieros protegidos
                protected = {
                    'transaction_type', 'amount', 'direction',
                    'wallet_id', 'balance_before', 'balance_after',
                }
                if any(k in vals for k in protected):
                    raise UserError(_(
                        'No se puede modificar una transacción confirmada '
                        '(%s). Debe crear una transacción de reversión.'
                    ) % rec.name)
        return super().write(vals)

    # ── Transiciones de estado ───────────────────────────────────────
    def action_confirm(self):
        """Confirmar transacción con validación completa de integridad."""
        # Tolerancia de 0.5 centavo para comparación monetaria de float
        DELTA = 0.005
        for rec in self:
            if rec.state not in ('draft', 'pending'):
                raise UserError(_(
                    'Solo transacciones en borrador o pendientes '
                    'pueden confirmarse.'
                ))

            # Validar que los campos numéricos estén inicializados.
            # 0.0 ES un valor válido (saldo cero); None/False no lo es.
            if rec.balance_before is None or rec.balance_before is False:
                raise ValidationError(_(
                    'balance_before no está inicializado para la '
                    'transacción %s.'
                ) % rec.name)
            if rec.balance_after is None or rec.balance_after is False:
                raise ValidationError(_(
                    'balance_after no está inicializado para la '
                    'transacción %s.'
                ) % rec.name)
            if rec.amount is None or rec.amount is False:
                raise ValidationError(_(
                    'amount no está inicializado para la transacción %s.'
                ) % rec.name)

            # amount > 0 ya está cubierto por la constraint SQL,
            # pero re-validamos por claridad
            if rec.amount <= 0:
                raise ValidationError(_(
                    'El monto debe ser mayor a cero (transacción %s).'
                ) % rec.name)

            # Coherencia aritmética
            if rec.direction == 'credit':
                expected = rec.balance_before + rec.amount
            else:  # debit
                expected = rec.balance_before - rec.amount

            if abs(rec.balance_after - expected) > DELTA:
                raise ValidationError(_(
                    'Incoherencia aritmética en la transacción %(xt)s:\n'
                    '  balance_before = %(before)s\n'
                    '  amount          = %(amount)s\n'
                    '  direction       = %(dir)s\n'
                    '  balance_after   = %(after)s (se esperaba %(expected)s)'
                ) % {
                    'tx': rec.name,
                    'before': rec.balance_before,
                    'amount': rec.amount,
                    'dir': rec.direction,
                    'after': rec.balance_after,
                    'expected': expected,
                })

            rec.state = 'confirmed'

    def action_cancel(self):
        for rec in self:
            if rec.state == 'confirmed':
                raise UserError(_(
                    'No se puede cancelar una transacción confirmada. '
                    'Debe crear una transacción de reversión.'
                ))
            rec.state = 'cancelled'

    def action_set_pending(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    'Solo transacciones en borrador pueden pasar a pendiente.'
                ))
            rec.state = 'pending'

    def action_draft(self):
        for rec in self:
            if rec.state in ('confirmed', 'reversed'):
                raise UserError(_(
                    'No se puede volver a borrador una transacción '
                    'confirmada o reversada.'
                ))
            rec.state = 'draft'

    # ── Reversión ───────────────────────────────────────────────────
    def action_reverse(self, note=None):
        """Crear transacción compensatoria append-only que revierte esta.

        Delega todo movimiento monetario a casino.money.flow.
        NO escribe balance_game ni wallet.balance directamente.

        - Solo transacciones 'confirmed' pueden revertirse.
        - Idempotencia: si ya existe reversión para esta tx, la devuelve.
        - La compensatoria se crea vía process_operation() bajo SELECT FOR UPDATE.
        - Link bidireccional mediante reversed_tx_id / reversal_tx_id.
        """
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError(_(
                'Solo transacciones confirmadas pueden revertirse. '
                'Estado actual: %s'
            ) % self.state)

        # Idempotencia: si ya fue revertida, devolver la existente
        existing = self.env['casino.wallet.transaction'].sudo().search([
            ('reversed_tx_id', '=', self.id),
        ], limit=1)
        if existing:
            return existing

        # Dirección compensatoria
        reverse_direction = 'credit' if self.direction == 'debit' else 'debit'

        # ═══════════════════════════════════════════════════════════
        # Delegar al servicio central — ÚNICO writer monetario.
        # process_operation() ejecuta:
        #   SELECT FOR UPDATE → invalida cache → lee balance →
        #   valida fondos → calcula after → crea tx draft →
        #   action_confirm() → write balance_game → sync wallet
        # ═══════════════════════════════════════════════════════════
        reverse_tx = self.env['casino.money.flow'].process_operation(
            operation_type=self.transaction_type,
            partner_id=self.wallet_id.partner_id,
            amount=self.amount,
            wallet_id=self.wallet_id.id,
            direction_override=reverse_direction,
            idempotency_key='REV-%s' % self.name,
            reversed_tx_id=self.id,
            reference='REV-%s' % self.name,
            note=note or _('Reversión de %s') % self.name,
            origin_model='casino.wallet.transaction',
            origin_id=self.id,
        )

        # Link bidireccional — marca la original como revertida.
        # write() permite esta transición específica (confirmed → reversed
        # + reversal_tx_id) como única excepción a la inmutabilidad.
        self.write({
            'state': 'reversed',
            'reversal_tx_id': reverse_tx.id,
        })

        return reverse_tx

    # ── Helpers ─────────────────────────────────────────────────────
    def _get_dirty_fields(self):
        """Devuelve los campos modificados respecto al origen."""
        if not self._origin:
            return set()
        dirty = set()
        for field_name in self._fields:
            if field_name in ('id', 'create_date', 'write_date',
                              '__last_update'):
                continue
            if (getattr(self, field_name)
                    != getattr(self._origin, field_name)):
                dirty.add(field_name)
        return dirty