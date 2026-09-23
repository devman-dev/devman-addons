"""casino.wallet — Billetera de fichas de una entidad (jugador, agente, sistema)."""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CasinoWallet(models.Model):
    _name = 'casino.wallet'
    _description = 'Casino Wallet'
    _order = 'id desc'

    # ── Identificación ──────────────────────────────────────────────
    name = fields.Char(
        string='Nombre',
        compute='_compute_name',
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Titular',
        required=True,
        index=True,
        ondelete='restrict',
        help='Partner dueño de esta billetera.',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario',
        compute='_compute_user_id',
        readonly=True,
        store=False,
        help='Usuario Odoo vinculado al partner (primero disponible).',
    )
    wallet_type = fields.Selection(
        selection=[
            ('player', 'Jugador'),
            ('agent', 'Agente'),
            ('system', 'Sistema'),
        ],
        string='Tipo de Wallet',
        required=True,
        default='player',
        index=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        default=0.0,
        help='Balance actual de fichas.',
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañía',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    # ── Relaciones ──────────────────────────────────────────────────
    transaction_ids = fields.One2many(
        comodel_name='casino.wallet.transaction',
        inverse_name='wallet_id',
        string='Transacciones',
    )

    # ── Restricciones ───────────────────────────────────────────────
    _sql_constraints = [
        (
            'casino_wallet_partner_unique',
            'unique(partner_id, wallet_type, company_id)',
            'Ya existe una billetera de este tipo para este partner en esta compañía.',
        ),
    ]

    @api.constrains('partner_id')
    def _check_partner_exists(self):
        for rec in self:
            if not rec.partner_id:
                raise ValidationError(_('El wallet debe tener un partner asignado.'))

    @api.constrains('company_id')
    def _check_company_exists(self):
        for rec in self:
            if not rec.company_id:
                raise ValidationError(_('El wallet debe pertenecer a una compañía.'))

    # ── Computes ────────────────────────────────────────────────────
    @api.depends('partner_id', 'wallet_type')
    def _compute_name(self):
        for rec in self:
            if rec.partner_id and rec.wallet_type:
                rec.name = f'{rec.partner_id.display_name} — {rec.get_wallet_type_label()}'
            else:
                rec.name = 'Nuevo Wallet'

    @api.depends('partner_id.user_ids')
    def _compute_user_id(self):
        for rec in self:
            rec.user_id = rec.partner_id.user_ids[:1].id if rec.partner_id.user_ids else False


    def _compute_balance(self):
        """Sincroniza wallet.balance desde partner.balance_game.

        balance_game es la fuente de verdad absoluta del saldo del
        jugador. wallet.balance se mantiene en espejo via write()
        en process_operation(); este metodo es fallback para
        re-sincronizacion batch.
        """
        for wallet in self:
            wallet.balance = wallet.partner_id.balance_game

    def get_wallet_type_label(self):
        """Devuelve la etiqueta legible del wallet_type."""
        labels = dict(self._fields['wallet_type'].selection)
        return labels.get(self.wallet_type, self.wallet_type)
