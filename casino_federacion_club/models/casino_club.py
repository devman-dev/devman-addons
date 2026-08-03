from odoo import fields, models, api

class CasinoClub(models.Model):
    # CASINO_FEDERATION_ODOO18: the original module inherited a model that
    # did not exist in any declared dependency. Define it here.
    _name = 'casino.club'
    _description = 'Club de Futbol'
    _order = 'federation_id, sequence, name'

    name = fields.Char(string='Nombre', required=True, index=True)
    short_name = fields.Char(string='Sigla', size=5)
    primary_color = fields.Char(string='Color principal', default='#073b2a')
    active = fields.Boolean(default=True)

    federation_id = fields.Many2one(
        'casino.federation', string='Federacion',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    logo = fields.Binary(string='Logo', attachment=True)
    commission = fields.Float(
        string='Comision (%)',
        default=0,
    )

    _sql_constraints = [
        ('casino_club_name_federation_uniq',
         'unique(name, federation_id)',
         'El club ya existe en esta federacion.'),
    ]
