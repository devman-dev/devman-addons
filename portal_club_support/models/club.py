"""Extiende casino.club para agregar logo/escudo desde portal."""

from odoo import models, fields


class CasinoClub(models.Model):
    _inherit = "casino.club"
    _order = "sequence, name"

    logo = fields.Image(
        string="Escudo",
        max_width=256,
        max_height=256,
        help="Logo/escudo del club para mostrar en el portal.",
    )
