"""Modelo de categoría de juego (Apostas Esportivas, Cassino Online, etc.)."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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
    require_selection = fields.Boolean(
        string="Selección Obligatoria",
        default=True,
        help="Si está marcado, el usuario debe elegir un club en esta categoría.",
    )

    # FEATURED_GAMES: configurable catalogue shown after the impact banner.
    featured_game_ids = fields.Many2many(
        comodel_name="product.template",
        relation="club_support_category_featured_game_rel",
        column1="category_id",
        column2="product_tmpl_id",
        string="Juegos a mostrar",
        domain="[('is_game', '=', True), ('active', '=', True), ('website_published', '=', True)]",
        help="Hasta tres juegos únicos pueden mostrarse en total en el panel JogaJunto.",
    )

    _sql_constraints = [
        (
            "unique_game_category_code",
            "UNIQUE(code)",
            "El código de categoría debe ser único.",
        ),
    ]

    @api.constrains("featured_game_ids", "active")
    def _check_featured_game_limit(self):
        """Keep the public dashboard layout to a maximum of three unique games."""
        selected_games = self.search([("active", "=", True)]).mapped("featured_game_ids")
        if len(selected_games) > 3:
            raise ValidationError(_("Puede seleccionar como máximo tres juegos destacados en total."))
