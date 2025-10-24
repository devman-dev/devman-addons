# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

class ProductFavorite(models.Model):
    _name = "casino.game.favorite"
    _description = "Producto favorito de usuario (Website)"
    _rec_name = "product_tmpl_id"
    _sql_constraints = [
        ("user_product_unique", "unique(user_id, product_tmpl_id)", "El producto ya está marcado como favorito por este usuario."),
    ]

    user_id = fields.Many2one("res.users", required=True, index=True, ondelete="cascade")
    partner_id = fields.Many2one("res.partner", related="user_id.partner_id", store=True)
    product_tmpl_id = fields.Many2one("product.template", required=True, index=True, ondelete="cascade")

    @api.model
    def toggle_favorite(self, product_tmpl_id):
        """Alterna favorito para el usuario actual. Requiere usuario autenticado (no público)."""
        user = self.env.user
        if user._is_public():
            raise AccessError(_("Debes iniciar sesión para usar favoritos."))
        fav = self.search([("user_id", "=", user.id), ("product_tmpl_id", "=", product_tmpl_id)], limit=1)
        if fav:
            fav.unlink()
            return {"favorited": False}
        self.create({"user_id": user.id, "product_tmpl_id": product_tmpl_id})
        return {"favorited": True}

    @api.model
    def is_favorited_batch(self, product_tmpl_ids):
        """Devuelve dict {tmpl_id: bool} para el usuario actual (no público)."""
        user = self.env.user
        if user._is_public():
            return {pid: False for pid in product_tmpl_ids}
        recs = self.read_group(
            domain=[("user_id", "=", user.id), ("product_tmpl_id", "in", product_tmpl_ids)],
            fields=["product_tmpl_id"],
            groupby=["product_tmpl_id"],
        )
        favored_ids = {r["product_tmpl_id"][0] for r in recs}
        return {pid: (pid in favored_ids) for pid in product_tmpl_ids}