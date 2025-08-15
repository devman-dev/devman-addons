from odoo import models, fields

class CasinoGameSession(models.Model):
    _name = 'casino.game.session'
    _description = 'Sesión de juego del jugador'

    game_id = fields.Many2one('product.product', string='Juego', required=True)
    user_id = fields.Many2one('res.users', string='Jugador', required=True)
    start_datetime = fields.Datetime(string='Inicio')
    end_datetime = fields.Datetime(string='Fin')
    amount = fields.Monetary(string='Monto', required=True)
    initial_balance = fields.Monetary(string='Saldo Inicial')
    final_balance = fields.Monetary(string='Saldo Final')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    result = fields.Selection([
        ('win', 'Ganó'),
        ('loss', 'Perdió'),
        ('draw', 'Empate'),
        ('abandoned', 'Abandonada')
    ], string='Resultado')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_progress', 'En curso'),
        ('finished', 'Finalizada'),
        ('error', 'Error')
    ], default='pending', string='Estado')
    description = fields.Text(string='Descripción')
    move_ids = fields.One2many('account.move', 'game_session_id', string='Movimientos')
