from odoo import models, fields, api


class CasinoLiquidationStat(models.Model):
    _name = 'casino.liquidation.stat'
    _description = 'Estadisticas de Liquidacion'
    _order = 'category_id'

    liquidation_id = fields.Many2one(
        'casino.liquidation',
        string='Liquidacion',
        required=True,
        ondelete='cascade'
    )
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoria',
        required=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        readonly=True
    )
    rounds_count = fields.Integer(
        string='Rondas',
        readonly=True
    )
    amount_bet = fields.Monetary(
        string='Bets',
        readonly=True,
        currency_field='currency_id'
    )
    profit = fields.Monetary(
        string='Profit',
        readonly=True,
        currency_field='currency_id'
    )
    payout_ratio = fields.Float(
        string='%Ratio',
        readonly=True,
        compute='_compute_payout_ratio',
        store=True
    )
    prob_payout = fields.Float(
        string='Prob. of payout',
        readonly=True,
        compute='_compute_prob_payout',
        store=True
    )
    wr_points = fields.Integer(
        string='WR Points',
        readonly=True
    )
    session_amount_signed = fields.Monetary(
        string='Total Neto',
        readonly=True,
        currency_field='currency_id'
    )

    @api.depends('amount_bet', 'profit')
    def _compute_payout_ratio(self):
        for rec in self:
            if rec.amount_bet and rec.amount_bet != 0:
                rec.payout_ratio = ((rec.amount_bet + rec.profit) / rec.amount_bet) * 100
            else:
                rec.payout_ratio = 0

    @api.depends('amount_bet', 'profit')
    def _compute_prob_payout(self):
        for rec in self:
            total = (rec.amount_bet or 0) + (rec.profit or 0)
            if total and total != 0:
                rec.prob_payout = (rec.profit / total) * 100
            else:
                rec.prob_payout = 0
