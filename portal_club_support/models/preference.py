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
        required=False,
        ondelete="set null",
        index=True,
    )
    club_id = fields.Many2one(
        comodel_name="casino.club",
        string="Club Elegido",
        required=True,
        ondelete="cascade",
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

    @api.depends("partner_id.name", "club_id.short_name")
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.partner_id.name:
                parts.append(rec.partner_id.name)
            if rec.club_id.short_name:
                parts.append(f"→ {rec.club_id.short_name}")
            rec.display_name = " | ".join(parts) if parts else "Preferencia"



    @api.model_create_multi
    def create(self, vals_list):
        """Al crear, desactivar cualquier preferencia previa del mismo usuario."""
        for vals in vals_list:
            partner_id = vals.get("partner_id")
            if partner_id:
                existing = self.search([
                    ("partner_id", "=", partner_id),
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
            "unique_active_preference_per_user",
            "UNIQUE(partner_id, active)",
            "Ya existe una preferencia activa para este usuario.",
        ),
    ]
