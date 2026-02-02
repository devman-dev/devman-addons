import logging

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools import safe_eval


class CasinoAccountMoveLineWizard(models.TransientModel):
    _name = 'casino.account.move.line.wizard'
    _description = 'Wizard de filtros para Cuenta Corriente Casino'

    _logger = logging.getLogger(__name__)

    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta')
    partner_id = fields.Many2one(
        'res.partner',
        string='Jugador',
        domain="[('is_player', '=', True)]"
    )

    @api.constrains('date_from', 'date_to')
    def _check_date_range(self):
        for record in self:
            if record.date_from and record.date_to and record.date_from > record.date_to:
                raise ValidationError('La fecha "Desde" no puede ser mayor que la fecha "Hasta".')

    def action_open_account_moves(self):
        self.ensure_one()
        action = self.env.ref('casino_online_back.action_casino_account_move_line').read()[0]
        domain = [
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            domain.append(('date', '<=', self.date_to))
        action['domain'] = domain
        # Preserve defaults from the action (e.g., search_default_group_by_partner)
        base_ctx = action.get('context')
        if isinstance(base_ctx, str):
            # Si el contexto es una cadena, evaluarla con safe_eval
            try:
                base_ctx = safe_eval(base_ctx) if base_ctx else {}
            except:
                base_ctx = {}
        elif not isinstance(base_ctx, dict):
            base_ctx = {}
        
        merged_ctx = dict(self.env.context or {})
        merged_ctx.update(base_ctx)
        merged_ctx['search_default_group_by_partner'] = 1
        action['context'] = merged_ctx
        
        self._logger.info(
            "Wizard action_open_account_moves context: %s | base_ctx: %s | env_ctx: %s",
            action.get('context'),
            base_ctx,
            self.env.context,
        )
        return action
