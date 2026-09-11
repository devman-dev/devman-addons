# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Safa KB @ Cybrosys, (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResUsersApprove(models.Model):
    """Store signup information pending admin approval.

    After approval, creates a res.users with full casino integration:
    - is_player = True on partner
    - agent_id assignment (selected by admin before approving)
    - casino.wallet creation (token + secret_token via casino_online)
    - Welcome bonus applied via casino.wallet.transaction (idempotent)
    - Plaintext password cleared from this record after user creation

    casino.money.flow is an AbstractModel — we create wallet and
    bonus transaction directly, following the same pattern as the
    money_flow service but inline.

    SECURITY: The password field stores the plaintext from the signup form
    temporarily. It is passed to res.users.create() which hashes it via
    _set_password(), then immediately cleared from this record.
    """
    _name = 'res.users.approve'
    _description = "Approval Request Details"

    name = fields.Char(help="Name of the user", string='Name')
    email = fields.Char(help="Email of the user", string="Email")
    password = fields.Char(
        help="Password for the new user. Passed to res.users.create() "
             "which hashes it via _set_password(), then cleared from "
             "this record. Never persisted long-term.",
        string="Password",
        copy=False,
    )
    for_approval_menu = fields.Boolean(
        string='For Approval Menu',
        default=False, readonly=True,
        help="Check the request is approved",
    )
    approved_date = fields.Datetime(
        string='Approved Date', copy=False,
        help="Approval date of signup request",
    )
    attachment_ids = fields.One2many(
        'user.approval.window',
        'approval_id',
        string='Attachments',
        help="Store uploaded documents",
    )
    hide_button = fields.Boolean(
        string='For hide button',
        default=False,
        help="Check the button is used or not",
    )

    # ── Casino integration fields ──────────────────────────────────
    agent_id = fields.Many2one(
        comodel_name='res.partner',
        string='Agente',
        domain="[('is_agent', '=', True)]",
        help="Agente responsable del jugador. Seleccionado por el "
             "administrador antes de aprobar.",
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner creado',
        readonly=True,
        copy=False,
        help="Partner asociado al usuario aprobado.",
    )
    wallet_id = fields.Many2one(
        comodel_name='casino.wallet',
        string='Wallet creada',
        readonly=True,
        copy=False,
        help="Wallet del jugador creada durante la aprobación.",
    )
    bonus_transaction_id = fields.Many2one(
        comodel_name='casino.wallet.transaction',
        string='Transacción de bono',
        readonly=True,
        copy=False,
        help="Transacción del bono de bienvenida aplicada.",
    )

    def action_approve_login(self):
        """Approve signup with full casino player integration.

        Single transactional flow (no cr.commit()):
        1. Create res.users (password hashed by Odoo)
        2. Clear plaintext password from approval record
        3. Set partner.is_player = True + agent_id
        4. Create casino.wallet inline (same logic as _find_or_create_wallet)
        5. Apply welcome bonus via casino.wallet.transaction (idempotent)
        6. Send welcome email

        casino.money.flow is an AbstractModel — all wallet/tx operations
        are done directly on the concrete models (casino.wallet,
        casino.wallet.transaction), following the same logic.
        """
        self.ensure_one()
        self.for_approval_menu = True
        self.hide_button = True

        user = self.env['res.users'].sudo().search(
            [('login', '=', self.email)],
            limit=1,
        )
        if not user:
            # Create user — password is hashed by Odoo's _set_password()
            user = self.env['res.users'].sudo().with_context(
                no_reset_password=True,
            ).create({
                'login': self.email,
                'name': self.name,
                'password': self.password,
                'groups_id': [(4, self.env.ref('base.group_portal').id)],
            })

            # Immediately clear plaintext password from approval record
            self.write({'password': False})

            # Send welcome email (outside critical path — catch errors)
            template = self.env.ref(
                'auth_signup.mail_template_user_signup_account_created',
                raise_if_not_found=False,
            )
            if template:
                try:
                    template.send_mail(
                        user.id,
                        email_values={'email_to': user.login},
                        force_send=True,
                    )
                except Exception:
                    _logger.warning(
                        "Failed to send welcome email to %s",
                        user.login, exc_info=True,
                    )

        partner = user.partner_id
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': self.name,
                'email': self.email,
                'user_ids': [(4, user.id)],
            })
            user.sudo().write({'partner_id': partner.id})

        # ── Sync partner as player + assign agent ──────────────────
        partner_vals = {'is_player': True}
        if self.agent_id:
            partner_vals['agent_id'] = self.agent_id.id
        partner.sudo().write(partner_vals)

        # ── Create wallet (inline _find_or_create_wallet logic) ────
        # casino.money.flow is AbstractModel — we create directly
        Wallet = self.env['casino.wallet'].sudo()
        company = self.env.company
        wallet = Wallet.search([
            ('partner_id', '=', partner.id),
            ('wallet_type', '=', 'player'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not wallet:
            wallet = Wallet.create({
                'partner_id': partner.id,
                'wallet_type': 'player',
                'company_id': company.id,
            })
            _logger.info(
                "Auto-created player wallet for partner %s (id=%s)",
                partner.id, wallet.id,
            )

        # ── Apply welcome bonus (idempotent) ──────────────────────
        bonus_amount = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'website_signup_approval.signup_bonus_amount',
                '0.0',
            )
        )
        bonus_tx = None
        if bonus_amount > 0:
            idempotency_key = f"signup_bonus_approval_{self.id}"
            Tx = self.env['casino.wallet.transaction'].sudo()

            # Idempotency check
            existing = Tx.search([
                ('idempotency_key', '=', idempotency_key),
            ], limit=1)
            if existing and existing.state == 'confirmed':
                bonus_tx = existing
                _logger.info(
                    "Idempotent replay: bonus tx %s for approval #%s",
                    existing.name, self.id,
                )
            elif not existing:
                try:
                    # Lock partner row
                    self.env.cr.execute(
                        "SELECT id FROM res_partner WHERE id = %s FOR UPDATE",
                        [partner.id],
                    )
                    partner.invalidate_recordset(['balance_game'])
                    balance_before = partner.balance_game
                    balance_after = balance_before + bonus_amount

                    bonus_tx = Tx.create({
                        'wallet_id': wallet.id,
                        'transaction_type': 'bonus',
                        'amount': bonus_amount,
                        'direction': 'credit',
                        'balance_before': balance_before,
                        'balance_after': balance_after,
                        'reference': (
                            f'Bono bienvenida: {partner.display_name} '
                            f'(aprobación #{self.id})'
                        ),
                        'origin_model': 'res.users.approve',
                        'origin_id': self.id,
                        'note': (
                            f'Welcome bonus of {bonus_amount} applied on '
                            f'signup approval #{self.id}'
                        ),
                        'idempotency_key': idempotency_key,
                        'state': 'draft',
                    })
                    bonus_tx.action_confirm()

                    # Update balances after confirm
                    partner.write({'balance_game': balance_after})
                    wallet.write({'balance': balance_after})

                    _logger.info(
                        "Welcome bonus applied: %s to partner %s "
                        "(approval #%s, tx=%s)",
                        bonus_amount, partner.id, self.id, bonus_tx.name,
                    )
                except Exception:
                    _logger.warning(
                        "Welcome bonus for approval #%s failed",
                        self.id, exc_info=True,
                    )

        # ── Record results on approval record ──────────────────────
        self.write({
            'partner_id': partner.id,
            'wallet_id': wallet.id,
            'bonus_transaction_id': bonus_tx.id if bonus_tx else False,
            'approved_date': fields.Datetime.now(),
        })

    def action_reject_login(self):
        """Reject the signup request and delete any existing user."""
        self.ensure_one()
        self.for_approval_menu = False
        self.hide_button = True
        user = self.env['res.users'].sudo().search(
            [('login', '=', self.email)],
            limit=1,
        )
        if user:
            user.sudo().unlink()