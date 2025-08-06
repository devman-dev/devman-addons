from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    game_session_id = fields.Many2one('casino.game.session', string='Sesión de Juego')

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
    
    amount_signed = fields.Monetary(
        string='Importe con Signo',
        compute='_compute_amount_signed',
        currency_field='currency_id'
    )
    
    @api.depends('debit', 'credit', 'move_id.move_type')
    def _compute_amount_signed(self):
        for line in self:
            if line.move_id.move_type in ('out_invoice', 'in_refund'):
                # Facturas: positivo
                line.amount_signed = line.debit - line.credit
            elif line.move_id.move_type in ('out_refund', 'in_invoice'):
                # Notas de crédito: negativo
                line.amount_signed = line.credit - line.debit
            elif line.move_id.move_type == 'entry' and line.payment_id:
                # Pagos: negativo
                line.amount_signed = -(line.debit - line.credit)
            else:
                # Otros movimientos
                line.amount_signed = line.debit - line.credit
