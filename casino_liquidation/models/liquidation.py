from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class CasinoLiquidation(models.Model):
    _name = 'casino.liquidation'
    _description = 'Liquidación de Casino'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Campos de secuencia
    name = fields.Char(
        string='Referencia',
        readonly=True,
        copy=False,
        default=lambda self: self.env['ir.sequence'].next_by_code('casino.liquidation')
    )

    # Estados
    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmada'),
            ('cancelled', 'Cancelada'),
        ],
        string='Estado',
        default='draft',
        readonly=True,
        tracking=True
    )

    # Fechas del filtro
    date_from = fields.Date(
        string='Fecha Desde',
        required=True
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True
    )

    # Proveedor
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        tracking=True
    )

    # Categoría
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        help='Categoría de productos'
    )

    # Líneas de liquidación
    line_ids = fields.One2many(
        'casino.liquidation.line',
        'liquidation_id',
        string='Detalles de Liquidación'
    )
    stat_line_ids = fields.One2many(
        'casino.liquidation.stat',
        'liquidation_id',
        string='Estadisticas',
        readonly=True
    )


    # Totales
    total_sessions = fields.Integer(
        string='Total Sesiones',
        compute='_compute_totals',
        store=True
    )
    total_session_amount = fields.Float(
        string='Total Importe Sesiones',
        compute='_compute_totals',
        store=True
    )
    total_commission = fields.Float(
        string='Total Comisiones',
        compute='_compute_totals',
        store=True
    )
    total_net = fields.Float(
        string='Total Neto a Liquidar',
        compute='_compute_totals',
        store=True
    )

    # Metadata
    created_by = fields.Many2one(
        'res.users',
        string='Creado por',
        readonly=True,
        default=lambda self: self.env.user
    )
    confirmed_by = fields.Many2one(
        'res.users',
        string='Confirmado por',
        readonly=True,
        tracking=True
    )
    confirmed_date = fields.Datetime(
        string='Fecha de Confirmación',
        readonly=True,
        tracking=True
    )
    notes = fields.Text(
        string='Notas'
    )

    @api.depends('line_ids', 'line_ids.session_amount', 'line_ids.commission_amount', 'line_ids.net_amount')
    def _compute_totals(self):
        for liquidation in self:
            liquidation.total_sessions = len(liquidation.line_ids)
            liquidation.total_session_amount = sum(liquidation.line_ids.mapped('session_amount'))
            liquidation.total_commission = sum(liquidation.line_ids.mapped('commission_amount'))
            liquidation.total_net = sum(liquidation.line_ids.mapped('net_amount'))

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise ValidationError('La fecha desde no puede ser mayor a la fecha hasta')

    def write(self, vals):
        res = super().write(vals)
        if 'line_ids' in vals:
            self._rebuild_stat_lines()
        return res

    def action_confirm(self):
        """Confirmar la liquidación"""
        if self.state != 'draft':
            raise UserError('Solo se pueden confirmar liquidaciones en estado Borrador')

        if not self.line_ids:
            raise UserError('No hay sesiones para liquidar en el período seleccionado')

        self.write({
            'state': 'confirmed',
            'confirmed_by': self.env.user.id,
            'confirmed_date': datetime.now(),
        })

        # Log en chatter
        self.message_post(
            body=f'Liquidación confirmada por {self.env.user.name}. '
                 f'Total a liquidar: ${self.total_commission:,.2f}'
        )

    def action_cancel(self):
        """Cancelar la liquidación"""
        if self.state == 'cancelled':
            raise UserError('Esta liquidación ya está cancelada')

        self.write({'state': 'cancelled'})
        self.message_post(body='Liquidación cancelada')

    def action_draft(self):
        """Volver a borrador"""
        self.write({
            'state': 'draft',
            'confirmed_by': False,
            'confirmed_date': False,
        })

    def unlink(self):
        """Solo se pueden eliminar liquidaciones en borrador"""
        if any(liq.state != 'draft' for liq in self):
            raise UserError('Solo se pueden eliminar liquidaciones en estado Borrador')
        return super().unlink()

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.name} - {record.provider_id.name} ({record.date_from} a {record.date_to})'
            result.append((record.id, name))
        return result

    def _rebuild_stat_lines(self):
        for record in self:
            record.stat_line_ids.unlink()
            if not record.line_ids:
                continue
            grouped = {}
            for line in record.line_ids:
                category = line.category_id
                if not category:
                    continue
                key = category.id
                data = grouped.setdefault(key, {
                    'liquidation_id': record.id,
                    'category_id': category.id,
                    'currency_id': line.currency_id.id,
                    'rounds_count': 0,
                    'amount_bet': 0.0,
                    'profit': 0.0,
                    'wr_points': 0,
                    'session_amount_signed': 0.0,
                })
                data['rounds_count'] += 1
                data['amount_bet'] += line.amount_bet or 0.0
                profit = line.profit or 0.0
                if line.result in ('loss', 'in_progress'):
                    profit = -profit
                data['profit'] += profit
                data['wr_points'] += line.wr_points or 0
                data['session_amount_signed'] += line.session_amount_signed or 0.0
            if grouped:
                record.stat_line_ids = [(0, 0, vals) for vals in grouped.values()]

    def action_generate_lines(self):
        """Genera (o regenera) las líneas de la liquidación usando los criterios
        de fecha, proveedor y categoría. Reemplaza cualquier línea existente.
        """
        for record in self:
            if record.state != 'draft':
                raise UserError('Solo se pueden generar líneas en estado Borrador')
            if not (record.date_from and record.date_to):
                raise UserError('Debe completar Fecha Desde, Fecha Hasta, Proveedor y Categoría')

            # Buscar sesiones finalizadas dentro del rango y que coincidan proveedor y categoría
            domain = [
                ('start_datetime', '>=', fields.Datetime.to_datetime(record.date_from)),
                ('end_datetime', '<=', fields.Datetime.to_datetime(record.date_to)),
                ('state', 'ilike', 'finished'),
            ]
            if record.provider_id:
                domain.append(('game_id.product_tmpl_id.provider_id', '=', record.provider_id.id))
            if record.category_id:
                # Filtrar juegos que tengan la categoría seleccionada
                domain.append(('game_id.product_tmpl_id.public_categ_ids', '=', record.category_id.id))
                
            sessions = self.env['casino.game.session'].search(domain)
            _logger.info('Sesiones encontradas para liquidación %s: %s', record.id, sessions.ids)
            _logger.info('Sessions data: %s', [(s.id, s.game_id.id, s.game_id.product_tmpl_id.provider_id.id, s.amount, s.state) for s in sessions])

            if not sessions:
                _logger.warning('No se encontraron sesiones para liquidación %s con dominio %s', record.id, domain)

            # Obtener configuración de comisión específica
            commission_config = self.env['casino.commission.config'].search([
                ('provider_id', '=', record.provider_id.id),
                ('category_id', '=', record.category_id.id),
                ('active', '=', True),
            ], limit=1)

            commission = commission_config.commission_percentage if commission_config else 35.0
            if not commission_config:
                _logger.warning('Usando comisión por defecto 35%% para liquidación %s (sin configuración específica)', record.id)
            else:
                _logger.info('Comisión %s%% aplicada en liquidación %s', commission, record.id)

            # Construir nuevas líneas
            line_vals = []
            for session in sessions:
                # Obtener la categoría que coincide con el filtro, o la primera disponible
                game_categories = session.game_id.product_tmpl_id.public_categ_ids
                
                # Intentar usar la categoría que coincide con el filtro de la liquidación
                session_category = record.category_id if record.category_id in game_categories else (game_categories[:1] if game_categories else False)
                
                line_vals.append((0, 0, {
                    'liquidation_id': record.id,
                    'session_id': session.id,
                    'category_id': session_category.id if session_category else False,
                    'commission_percentage': commission,
                }))

            # Reemplazar líneas existentes
            record.write({'line_ids': [(5, 0, 0)] + line_vals})
            record._rebuild_stat_lines()
            _logger.info('Liquidación %s: %s líneas generadas', record.id, len(line_vals))

        return True