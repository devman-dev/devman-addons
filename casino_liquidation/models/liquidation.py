from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime


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
        required=True,
        tracking=True
    )

    # Categoría
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        required=True,
        help='Categoría de productos'
    )

    # Líneas de liquidación
    line_ids = fields.One2many(
        'casino.liquidation.line',
        'liquidation_id',
        string='Detalles de Liquidación'
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
                 f'Total a liquidar: ${self.total_net:,.2f}'
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