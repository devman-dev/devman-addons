"""Extensión de res.partner con campos para el portal JogaJunto."""

from odoo import models, fields


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_br_cpf = fields.Char(
        string="CPF",
        size=14,
        help="Cadastro de Pessoas Físicas (Brasil). "
             "Se instala l10n_br, este campo se oculta para evitar duplicados.",
    )
    birth_date = fields.Date(
        string="Data de Nascimento",
    )
    age_confirmed = fields.Boolean(
        string="Maior de 18 anos",
        default=False,
        help="El usuario confirmó ser mayor de 18 años.",
    )
    terms_accepted_date = fields.Datetime(
        string="Termos Aceitos em",
        readonly=True,
    )
    preferences_count = fields.Integer(
        string="Preferências Ativas",
        compute="_compute_preferences_count",
    )

    def _compute_preferences_count(self):
        """Contar preferencias activas del portal user actual."""
        for partner in self:
            partner.preferences_count = self.env["club.support.preference"].search_count([
                ("partner_id", "=", partner.id),
                ("active", "=", True),
            ])
