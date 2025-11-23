from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class GenerateLiquidationWizard(models.TransientModel):
    _name = 'casino.liquidation.wizard'
    _description = 'Asistente para Generar Liquidación'

    date_from = fields.Date(
        string='Fecha Desde',
        required=True
    )
    date_to = fields.Date(
        string='Fecha Hasta',
        required=True
    )
    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True
    )
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        required=True,
        help='Categoría de productos a liquidar'
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise UserError('La fecha desde no puede ser mayor a la fecha hasta')

    def action_generate_liquidation(self):
        """Generar la liquidación con todas las sesiones del período"""
        self.ensure_one()

        # Usar la liquidación activa si el wizard fue abierto desde un registro
        ctx = self.env.context or {}
        liquidation = None
        if ctx.get('active_model') == 'casino.liquidation' and ctx.get('active_id'):
            liq = self.env['casino.liquidation'].browse(ctx['active_id'])
            if liq.exists():
                liquidation = liq

        if liquidation:
            # Actualizar cabecera con los valores elegidos en el asistente
            liquidation.write({
                'date_from': self.date_from,
                'date_to': self.date_to,
                'provider_id': self.provider_id.id,
                'category_id': self.category_id.id,
            })
            _logger.info('Actualizando liquidación existente %s con rango %s - %s, proveedor %s, categoría %s',
                         liquidation.id, self.date_from, self.date_to, self.provider_id.id, self.category_id.id)
        else:
            # Crear un nuevo registro de liquidación si no se abrió desde una existente
            liquidation_vals = {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'provider_id': self.provider_id.id,
                'category_id': self.category_id.id,
            }
            liquidation = self.env['casino.liquidation'].create(liquidation_vals)
            _logger.info(
                'Liquidación creada con ID %s, proveedor %s, categoría %s, período %s a %s',
                liquidation.id, self.provider_id.id, self.category_id.id, self.date_from, self.date_to
            )
        # Buscar sesiones en el período que pertenezcan a juegos de este proveedor y categoría
        try:
            sessions = self.env['casino.game.session'].search([
                ('game_id.product_tmpl_id.provider_id', '=', self.provider_id.id),
                ('game_id.product_tmpl_id.public_categ_ids', 'in', [self.category_id.id]),
                ('start_datetime', '>=', fields.Datetime.to_datetime(self.date_from)),
                ('start_datetime', '<=', fields.Datetime.to_datetime(self.date_to)),
                ('state', '=', 'finished'),  # Solo sesiones finalizadas
            ])
            _logger.info('Sesiones encontradas para liquidación %s: %s', liquidation.id, sessions.ids)
        except Exception as e:
            _logger.error(f'Error al buscar sesiones: {e}')
            raise UserError(f'Error al buscar sesiones: {e}')

        # if not sessions:
        #     raise UserError(
        #         f'No hay sesiones finalizadas para el proveedor {self.provider_id.name} '
        #         f'y categoría {self.category_id.name} en el período {self.date_from} a {self.date_to}'
        #     )

        # Buscar configuración de comisión para este proveedor y categoría
        commission_config = self.env['casino.commission.config'].search([
            ('provider_id', '=', self.provider_id.id),
            ('category_id', '=', self.category_id.id),
            ('active', '=', True),
        ], limit=1)

        if not commission_config:
            commission = 35
            _logger.warning('Usando comisión por defecto 35%% para %s - %s', self.provider_id.name, self.category_id.name)
        else:
            commission = commission_config.commission_percentage

        # Generar líneas de liquidación
        line_vals_list = []
        for session in sessions:
            # Obtener la categoría que coincide con el filtro, o la primera disponible
            game_categories = session.game_id.product_tmpl_id.public_categ_ids
            session_category = self.category_id if self.category_id in game_categories else (game_categories[:1] if game_categories else False)
            
            line_vals = {
                'liquidation_id': liquidation.id,
                'session_id': session.id,
                'category_id': session_category.id if session_category else False,
                'commission_percentage': commission,
            }
            line_vals_list.append((0, 0, line_vals))

        # Reemplazar líneas en la liquidación (limpiar y cargar nuevas)
        if line_vals_list:
            liquidation.write({'line_ids': [(5, 0, 0)] + line_vals_list})

        # Retornar la vista de la liquidación creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'casino.liquidation',
            'res_id': liquidation.id,
            'view_mode': 'form',
            'target': 'current',
        }