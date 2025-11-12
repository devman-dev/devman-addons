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
    session_date = fields.Datetime(
        string='Fecha de Sesión',
        readonly=True,
        related='session_id.start_datetime'
    )
    game_id = fields.Many2one(
        'product.product',
        string='Juego',
        readonly=True,
        related='session_id.game_id'
    )
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        readonly=True,
        help='Categoría del producto/juego'
    )
    session_amount = fields.Monetary(
        string='Importe Sesión (BET)',
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

    @api.depends('session_amount', 'commission_percentage')
    def _compute_commission_amount(self):
        for line in self:
            line.commission_amount = line.session_amount * (line.commission_percentage / 100)

    @api.depends('session_amount', 'commission_amount')
    def _compute_net_amount(self):
        for line in self:
            line.net_amount = line.session_amount - line.commission_amount

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.session_date} - {record.game_id.name} - ${record.session_amount:.2f}'
            result.append((record.id, name))
        return result