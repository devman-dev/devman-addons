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
        
        # Crear el registro de liquidación
        liquidation_vals = {
            'date_from': self.date_from,
            'date_to': self.date_to,
            'provider_id': self.provider_id.id,
            'category_id': self.category_id.id,
        }
        liquidation = self.env['casino.liquidation'].create(liquidation_vals)
        _logger.info(f'Liquidación creada con ID {liquidation.id}, categoria {self.category_id.id}: {self.category_id.name}, proveedror {self.provider_id.id}: {self.provider_id.name}, categoría {self.category_id.name}, período {self.date_from} a {self.date_to}')
        # Buscar sesiones en el período que pertenezcan a juegos de este proveedor y categoría
        try:
            sessions = self.env['casino.game.session'].search([
                ('game_id.product_tmpl_id.provider_id', '=', self.provider_id.id),
                # Filtrado por categoría debe ir vía product_tmpl_id
                # ('game_id.product_tmpl_id.public_categ_ids', 'in', [self.category_id.id]),
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
            # ('category_id', '=', self.category_id.id),
            ('active', '=', True),
        ], limit=1)

        if not commission_config:
            commission = 35
            # raise UserError(
            #     f'No hay configuración de comisión para {self.provider_id.name} - {self.category_id.name}'
            # )
        else:
            commission = commission_config.commission_percentage

        # Generar líneas de liquidación
        line_vals_list = []
        for session in sessions:
            line_vals = {
                'liquidation_id': liquidation.id,
                'session_id': session.id,
                'category_id': self.category_id.id,
                'commission_percentage': commission,
            }
            line_vals_list.append((0, 0, line_vals))

        # Agregar todas las líneas a la liquidación
        if line_vals_list:
            liquidation.write({'line_ids': line_vals_list})

        # Retornar la vista de la liquidación creada
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'casino.liquidation',
            'res_id': liquidation.id,
            'view_mode': 'form',
            'target': 'current',
        }