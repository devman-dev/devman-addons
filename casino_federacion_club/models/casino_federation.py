from odoo import fields, models, api

class CasinoFederation(models.Model):
    _name = 'casino.federation'
    _description = 'Federacion de Clubes'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True)
    logo = fields.Binary(string='Logo')
    active = fields.Boolean(default=True)
    commission = fields.Float(
        string='Comision (%)',
        help='Porcentaje de comision aplicable a todos los clubes de esta federacion (entero)',
        default=0,
    )
    club_ids = fields.One2many('casino.club', 'federation_id', string='Clubes')
    club_count = fields.Integer(string='Cantidad de Clubes', compute='_compute_club_count')

    @api.depends('club_ids')
    def _compute_club_count(self):
        for fed in self:
            fed.club_count = len(fed.club_ids)

    _sql_constraints = [
        ('casino_federation_name_uniq', 'unique(name)',
         'La federacion ya existe.'),
    ]
