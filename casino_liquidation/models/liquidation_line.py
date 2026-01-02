from odoo import models, fields, api


class CasinoLiquidationLine(models.Model):
    _name = 'casino.liquidation.line'
    _description = 'Línea de Detalle de Liquidación'
    _order = 'liquidation_id, session_date'

    liquidation_id = fields.Many2one(
        'casino.liquidation',
        string='Liquidación',
        required=True,
        ondelete='cascade'
    )
    session_id = fields.Many2one(
        'casino.game.session',
        string='Sesión',
        readonly=True,
        help='Referencia a la sesión de juego'
    )
    
    # Campo de transacción (basado en casino_game_session.transaction_id)
    transaction_id = fields.Text(
        string='Ticket',
        readonly=True,
        related='session_id.transaction_id',
        help='ID de transacción de la sesión de juego'
    )

    # Campo CID - Nickname del jugador de la sesión
    cid = fields.Char(
        string='CID',
        readonly=True,
        related='session_id.user_id.nickname',
        help='Nickname del jugador de la sesión'
    )
    
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        help='Categoría del producto/juego'
    )
    
    game_id = fields.Many2one(
        'product.product',
        string='Juego',
        readonly=True,
        related='session_id.game_id'
    )

    session_date = fields.Datetime(
        string='Fecha de Sesión',
        readonly=True,
        related='session_id.start_datetime'
    )

    session_amount = fields.Monetary(
        string='Monto',
        readonly=True,
        help='Importe total de la sesión',
        related='session_id.amount',
        currency_field='currency_id'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True,
        related='session_id.currency_id'
    )
    
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        readonly=True,
        related='session_id.provider_id',
        help='Proveedor asociado al juego de la sesión'
    )

    round_id = fields.Text(
        string='ID Round',
        readonly=True,
        related='session_id.round_id',
        help='ID de la ronda de juego'
    )

    
    # Campo de juego/CID (basado en product_template.game_id)
    game_template_id = fields.Many2one(
        'product.template',
        string='CID2',
        readonly=True,
        related='session_id.game_id.product_tmpl_id',
        help='Game ID del producto plantilla'
    )
    
    commission_percentage = fields.Float(
        string='% Comisión',
        readonly=True,
        help='Porcentaje de comisión aplicado'
    )
    commission_amount = fields.Float(
        string='Monto Comisión',
        compute='_compute_commission_amount',
        store=True,
        readonly=True
    )
    net_amount = fields.Float(
        string='Monto Neto',
        compute='_compute_net_amount',
        store=True,
        readonly=True,
        help='Importe después de comisión'
    )
        
    # Campo amount relacionado
    amount = fields.Monetary(
        string='Amount',
        readonly=True,
        related='session_id.amount',
        currency_field='currency_id',
        help='Monto de la transacción'
    )
    
    # Campo result relacionado
    result = fields.Selection([
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('draw', 'Draw'),
        ('abandoned', 'Abandoned'),
        ('balance', 'Balance'),
        ('started', 'Started'),
        ('in_progress', 'Running')
    ], 
        string='Resultado',
        readonly=True,
        related='session_id.result',
        help='Resultado de la sesión'
    )
    
    # Bet: igual al amount si result es 'win'
    amount_bet = fields.Monetary(
        string='Bets',
        readonly=True,
        compute='_compute_amount_bet',
        store=True,
        currency_field='currency_id',
        help='Monto apostado (si result es win)'
    )

    # Profit: igual al amount si result es 'loss'
    profit = fields.Monetary(
        string='Profit',
        readonly=True,
        compute='_compute_profit',
        store=True,
        currency_field='currency_id',
        help='Ganancia/Pérdida (si result es loss)'
    )

    payout_ratio = fields.Float(
        string='%Ratio',
        readonly=True,
        compute='_compute_payout_ratio',
        store=True,
        help='Ratio de payout: ((Bets + Profit) / Bets) * 100'
    )

    prob_payout = fields.Float(
        string='Prob. of payout',
        readonly=True,
        compute='_compute_prob_payout',
        store=True,
        help='Probabilidad de payout: (Profit / (Bets + Profit)) * 100'
    )

    wr_points = fields.Integer(
        string='WR Points',
        help='Puntos de juego acumulados'
    )

    @api.depends('session_amount', 'commission_percentage')
    def _compute_commission_amount(self):
        for line in self:
            line.commission_amount = line.session_amount * (line.commission_percentage / 100)

    @api.depends('session_amount', 'commission_amount')
    def _compute_net_amount(self):
        for line in self:
            line.net_amount = line.session_amount - line.commission_amount

    @api.depends('session_id.amount', 'session_id.result')
    def _compute_amount_bet(self):
        """
        Bet es igual al amount si result es 'win'
        """
        for line in self:
            if line.session_id and line.session_id.result == 'win':
                line.amount_bet = line.session_id.amount or 0
            else:
                line.amount_bet = 0

    @api.depends('session_id.amount', 'session_id.result')
    def _compute_profit(self):
        """
        Profit es igual al amount si result es 'loss'
        """
        for line in self:
            if line.session_id and line.session_id.result == 'loss':
                line.profit = line.session_id.amount or 0
            else:
                line.profit = 0

    @api.depends('amount_bet', 'profit')
    def _compute_payout_ratio(self):
        """
        Calcula el ratio de payout: ((Bets + Profit) / Bets) * 100
        """
        for line in self:
            if line.amount_bet and line.amount_bet > 0:
                line.payout_ratio = ((line.amount_bet + line.profit) / line.amount_bet) * 100
            else:
                line.payout_ratio = 0

    @api.depends('amount_bet', 'profit')
    def _compute_prob_payout(self):
        """
        Calcula la probabilidad de payout: (Profit / (Bets + Profit)) * 100
        Representa el porcentaje de ganancia respecto al total apostado
        """
        for line in self:
            total = (line.amount_bet or 0) + (line.profit or 0)
            if total and total > 0:
                line.prob_payout = (line.profit / total) * 100
            else:
                line.prob_payout = 0

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.session_date} - {record.game_id.name} - ${record.session_amount:.2f}'
            result.append((record.id, name))
        return result
