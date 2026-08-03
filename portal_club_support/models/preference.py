"""Modelo de preferencia: club elegido por un usuario para una categoría."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Preference(models.Model):
    _name = "club.support.preference"
    _description = "Preferencia de Club"
    _order = "category_id, partner_id"
    _rec_name = "display_name"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Usuario",
        required=True,
        ondelete="cascade",
        index=True,
    )
    category_id = fields.Many2one(
        comodel_name="club.support.game.category",
        string="Categoría",
        required=True,
        ondelete="cascade",
        index=True,
    )
    club_id = fields.Many2one(
        comodel_name="club.support.club",
        string="Club Elegido",
        required=False,
        ondelete="cascade",
    )
    # FEDERATION_CLUB_PICKER: new catalogue-backed choice. Keep club_id for
    # backwards compatibility with preferences created by version 18.0.1.
    casino_club_id = fields.Many2one(
        comodel_name="casino.club",
        string="Club apoyado",
        ondelete="restrict",
        index=True,
    )
    # ODOO18_PORTAL_FIX: expose the nested value as a real related field for
    # list/form views.
    commission_percentage = fields.Float(
        string="Comissão (%)",
        related="club_id.commission_percentage",
        readonly=True,
    )
    active = fields.Boolean(
        string="Vigente",
        default=True,
    )
    selected_date = fields.Datetime(
        string="Fecha de Selección",
        default=fields.Datetime.now,
        readonly=True,
    )
    changed_date = fields.Datetime(
        string="Última Modificación",
        readonly=True,
    )
    display_name = fields.Char(
        string="Nombre",
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("partner_id.name", "category_id.name", "club_id.short_name",
                 "casino_club_id.short_name")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.partner_id.name:
                parts.append(rec.partner_id.name)
            if rec.category_id.name:
                parts.append(rec.category_id.name)
            selected_club = rec.casino_club_id or rec.club_id
            if selected_club:
                parts.append(f"→ {selected_club.short_name or selected_club.name}")
            rec.display_name = " | ".join(parts) if parts else "Preferencia"

    @api.constrains("club_id", "category_id")
    def _check_club_in_category(self):
        """Validar que el club pertenece a la categoría indicada."""
        for rec in self:
            if rec.club_id and rec.category_id:
                if rec.club_id not in rec.category_id.club_ids:
                    raise ValidationError(_(
                        "El club '%(club)s' no está disponible en la categoría '%(cat)s'.",
                        club=rec.club_id.name,
                        cat=rec.category_id.name,
                    ))

    @api.model_create_multi
    def create(self, vals_list):
        """Al crear, desactivar cualquier preferencia previa del mismo usuario y categoría."""
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            category_id = vals.get("category_id")
            if partner_id and category_id:
                existing = self.search([
                    ("partner_id", "=", partner_id),
                    ("category_id", "=", category_id),
                    ("active", "=", True),
                ])
                if existing:
                    existing.write({"active": False, "changed_date": fields.Datetime.now()})
        return super().create(vals_list)

    def write(self, vals):
        if "club_id" in vals or "active" in vals:
            vals["changed_date"] = fields.Datetime.now()
        return super().write(vals)

    _sql_constraints = [
        (
            "unique_active_preference_per_user_category",
            "UNIQUE(partner_id, category_id, active)",
            "Ya existe una preferencia activa para este usuario en esta categoría.",
        ),
    ]
