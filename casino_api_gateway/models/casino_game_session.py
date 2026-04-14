from odoo import fields, models


class CasinoGameSession(models.Model):
    _inherit = "casino.game.session"

    provider_game_id = fields.Char(string="Game ID Proveedor")
    provider_request_payload_json = fields.Text(string="Payload Proveedor")
