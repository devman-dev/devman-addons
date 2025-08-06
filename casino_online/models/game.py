from odoo import models, fields

class CasinoGame(models.Model):
    _inherit = 'product.template'

    is_game = fields.Boolean(string='Es un juego')
    iframe_url = fields.Char(string='URL del iframe')
    provider_id = fields.Many2one('res.partner', string='Proveedor del juego')
    code = fields.Char(string='Código de integración')
