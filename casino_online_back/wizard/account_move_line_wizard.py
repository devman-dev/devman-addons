from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CasinoAccountMoveLineWizard(models.TransientModel):
    _name = 'casino.account.move.line.wizard'
    _description = 'Wizard de filtros para Cuenta Corriente Casino'

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
        action['context'] = dict(self.env.context or {})
        return action
