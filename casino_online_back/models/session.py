from odoo import models, fields, api

class CasinoGameSession(models.Model):
    _name = 'casino.game.session'
    _description = 'Sesión de juego del jugador'
    _order = "id desc"

    token = fields.Char(string='Token')
    game_id = fields.Many2one('product.product', string='Juego')
    endGame = fields.Boolean(string='Fin del Juego')
    round_id = fields.Text(string='Ronda')
    transaction_id = fields.Text(string='Transacción')
    amount = fields.Monetary(string='Monto')
    TokenLive = fields.Boolean(string='Token Live')

    user_id = fields.Many2one('res.users', string='Jugador', required=True)
    start_datetime = fields.Datetime(string='Inicio')
    end_datetime = fields.Datetime(string='Fin')
    initial_balance = fields.Monetary(string='Saldo Inicial')
    final_balance = fields.Monetary(string='Saldo Final')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    result = fields.Selection([
        ('win', 'Ganó'),
        ('loss', 'Perdió'),
        ('draw', 'Empate'),
        ('abandoned', 'Abandonada'),
        ('balance', 'Balance'),
        ('started', 'Started')
    ], string='Resultado')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('in_progress', 'En curso'),
        ('finished', 'Finalizada'),
        ('error', 'Error'),
        ('logged_in', 'Logged In')
    ], default='pending', string='Estado')
    description = fields.Text(string='Descripción')
    move_ids = fields.One2many('account.move', 'game_session_id', string='Movimientos')
    json_data = fields.Text(string='JSON Recibido')
    internal_transaction_id = fields.Text(string='Transacción Interna')

    group_display_name = fields.Char(
        string="Agrupación Detallada",
        compute="_compute_group_display_name",
        store=True
    )

    @api.depends('transaction_id', 'game_id', 'user_id', 'start_datetime')
    def _compute_group_display_name(self):
        for rec in self:
            rec.group_display_name = f"{rec.transaction_id or 'N/A'} - {rec.game_id.name or 'N/A'} - {rec.user_id.name or 'N/A'} - {rec.start_datetime.strftime('%Y-%m-%d %H:%M') if rec.start_datetime else 'N/A'}"
            