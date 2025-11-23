from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CasinoCommissionConfig(models.Model):
    _name = 'casino.commission.config'
    _description = 'Configuración de Comisiones por Proveedor y Categoría'
    _order = 'provider_id, category_id'

    provider_id = fields.Many2one(
        'res.partner',
        string='Proveedor',
        required=True,
        help='Proveedor del juego (Marca)'
    )
    category_id = fields.Many2one(
        'product.public.category',
        string='Categoría',
        required=True,
        help='Categoría de producto'
    )
    commission_percentage = fields.Float(
        string='% de Comisión',
        required=True,
        help='Porcentaje de comisión a aplicar sobre el importe'
    )
    active = fields.Boolean(
        string='Activo',
        default=True
    )
    notes = fields.Text(
        string='Notas'
    )

    _sql_constraints = [
        ('unique_provider_category',
         'UNIQUE(provider_id, category_id)',
         'Ya existe una configuración para este proveedor y categoría'),
        ('positive_commission',
         'CHECK(commission_percentage >= 0)',
         'El porcentaje de comisión debe ser positivo'),
    ]

    @api.constrains('commission_percentage')
    def _check_commission_percentage(self):
        for record in self:
            if record.commission_percentage > 100:
                raise ValidationError(
                    f'El porcentaje de comisión no puede ser mayor a 100%'
                )

    def name_get(self):
        result = []
        for record in self:
            name = f'{record.provider_id.name} - {record.category_id.name} ({record.commission_percentage}%)'
            result.append((record.id, name))
        return result