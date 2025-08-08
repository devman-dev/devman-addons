from odoo import http
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
            return redirect(product.iframe_url)
        return request.render("website_sale.product", self._prepare_product_values(product, category, search, **kwargs))