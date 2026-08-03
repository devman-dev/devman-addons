"""Modelo de categoría de juego (Apostas Esportivas, Cassino Online, etc.)."""

from odoo import models, fields


class GameCategory(models.Model):
    _name = "club.support.game.category"
    _description = "Categoría de Juego"
    _order = "sequence, name"

    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
    )
    code = fields.Char(
        string="Código",
        required=True,
        help="Código único identificador de la categoría.",
    )
    description = fields.Text(
        string="Descripción",
        translate=True,
    )
    icon = fields.Char(
        string="Ícono",
        default="fa-gamepad",
        help="Clase CSS de FontAwesome para el ícono de la categoría.",
    )
    color = fields.Char(
        string="Color Principal",
        default="#1B5E20",
        help="Color hexadecimal para la identidad visual de la categoría.",
    )
    sequence = fields.Integer(
        string="Orden",
        default=10,
    )
    active = fields.Boolean(
        string="Activa",
        default=True,
    )
    commission_description = fields.Text(
        string="Descripción de Comisión",
        translate=True,
        help="Texto explicativo de cómo funciona la comisión para esta categoría.",
    )
    club_ids = fields.Many2many(
        comodel_name="club.support.club",
        relation="game_category_club_rel",
        column1="category_id",
        column2="club_id",
        string="Clubes Disponibles",
    )
    require_selection = fields.Boolean(
        string="Selección Obligatoria",
        default=True,
        help="Si está marcado, el usuario debe elegir un club en esta categoría.",
    )

    _sql_constraints = [
        (
            "unique_game_category_code",
            "UNIQUE(code)",
            "El código de categoría debe ser único.",
        ),
    ]
