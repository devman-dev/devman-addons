"""Modelo de club (Flamengo, Palmeiras, Corinthians, etc.)."""

from odoo import models, fields


class Club(models.Model):
    _name = "club.support.club"
    _description = "Club"
    _order = "sequence, name"

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
    )
    short_name = fields.Char(
        string="Abreviatura",
        help="Nombre corto o sigla del club (ej: FLA, PAL, COR).",
    )
    logo = fields.Image(
        string="Escudo",
        max_width=256,
        max_height=256,
    )
    primary_color = fields.Char(
        string="Color Principal",
        default="#000000",
        help="Color hexadecimal principal del club.",
    )
    secondary_color = fields.Char(
        string="Color Secundario",
        default="#FFFFFF",
        help="Color hexadecimal secundario del club.",
    )
    active = fields.Boolean(
        string="Activo",
        default=True,
    )
    sequence = fields.Integer(
        string="Orden",
        default=10,
    )
    category_ids = fields.Many2many(
        comodel_name="club.support.game.category",
        relation="game_category_club_rel",
        column1="club_id",
        column2="category_id",
        string="Categorías",
    )
    commission_percentage = fields.Float(
        string="Comisión (%)",
        digits=(5, 2),
        default=0.0,
        help="Porcentaje de comisión que recibe el club por las apuestas en sus categorías.",
    )
    website_url = fields.Char(
        string="Sitio Web",
        help="URL del sitio oficial del club.",
    )
