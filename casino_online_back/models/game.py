from odoo import models, fields

class CasinoGame(models.Model):
    _inherit = 'product.template'

    is_game = fields.Boolean(string='Es un juego')
    iframe_url = fields.Char(string='URL del iframe')
    provider_id = fields.Many2one('res.partner', string='Proveedor del juego')
    code = fields.Char(string='Código de integración')
    url_login = fields.Char(string='URL de login')
    url_debit= fields.Char(string='URL de débito') # ganada
    url_credit = fields.Char(string='URL de crédito') # perdida
    url_balance = fields.Char(string='URL de balance')
    agency_id = fields.Char(string='Id Agencia') #id agencia
    game_id = fields.Char(string='ID del juego en el proveedor')
