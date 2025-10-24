# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class WebsiteSaleFavorites(http.Controller):

    @http.route('/shop/favorite/toggle', type='json', auth='public', methods=['POST'], website=True)
    def toggle_favorite_json(self, product_id, **kwargs):
        """Endpoint JSON para alternar un favorito."""
        # Validar que el usuario esté autenticado
        if request.env.user._is_public():
            return {'error': 'Debes iniciar sesión para usar favoritos.', 'favorited': False}
        
        ProductFavorite = request.env['casino.game.favorite']
        return ProductFavorite.toggle_favorite(product_id)

    @http.route('/shop/favorites/status', type='json', auth='public', methods=['POST'], website=True)
    def get_favorites_status(self, product_ids, **kwargs):
        """Endpoint JSON para obtener el estado de múltiples favoritos."""
        ProductFavorite = request.env['casino.game.favorite']
        return ProductFavorite.is_favorited_batch(product_ids)

    @http.route("/my/favorites", type="http", auth="user", website=True, sitemap=True)
    def my_favorites(self, **kwargs):
        favs = request.env["casino.game.favorite"].sudo().search([("user_id", "=", request.env.user.id)])
        products = favs.mapped("product_tmpl_id").sudo().with_context(bin_size=True)
        values = {
            "products": products,
            "page_name": "my_favorites",
        }
        return request.render("casino_online_favorito.my_favorites_page", values)