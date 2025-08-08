from odoo import http
from datetime import datetime, timedelta
from odoo.http import request
from werkzeug.utils import redirect
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo import fields
from odoo.exceptions import UserError


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

            partner = user.partner_id

            if not product.property_account_income_id:
                raise UserError("El producto debe tener precio y cuenta de ingreso configurados.")

            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner.id,
                'invoice_date': fields.Date.today(),
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id,
                    'name': product.name,
                    'quantity': 1,
                    'price_unit': 100,
                    'account_id': product.property_account_income_id.id,
                })],
            }

            invoice = request.env['account.move'].sudo().create(invoice_vals)
            invoice.action_post()

            return redirect(product.iframe_url)
        return request.render("website_sale.product", self._prepare_product_values(product, category, search, **kwargs))