from odoo import http
from datetime import datetime, timedelta
from odoo.http import request
from werkzeug.utils import redirect
from odoo.addons.website_sale.controllers.main import WebsiteSale

class WebsiteShop(WebsiteSale):

    @http.route(['/shop/<model("product.template"):product>'], type='http', auth="public", website=True,
        sitemap=WebsiteSale.sitemap_products,
        readonly=True,
        override=True)
    def product(self, product, category='', search='', **kwargs):
        if not request.website.has_ecommerce_access():
            return request.redirect('/web/login')
        if product.iframe_url:
            user = request.env.user

            # Opcional: obtener balance inicial (ej. de wallet o cuenta)
            initial_balance = 0.0  # Actualiza con lógica real si aplica

            # Crear sesión
            session = request.env['casino.game.session'].sudo().create({
                'game_id': product.id,
                'user_id': user.id,
                'start_datetime': datetime.now(),
                'end_datetime': datetime.now() + timedelta(minutes=5),
                'initial_balance': 250,
                'final_balance': 100,
                'result': 'loss',
                'currency_id': user.company_id.currency_id.id,
                'state': 'finished',
                'description': f'Sesión iniciada por {user.name}'
            })
            return redirect(product.iframe_url)
        return request.render("website_sale.product", self._prepare_product_values(product, category, search, **kwargs))