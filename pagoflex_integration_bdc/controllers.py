from odoo import http
from odoo.http import request

class PagoflexAccountCloseController(http.Controller):
    @http.route('/account_close', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def account_close(self, **post):
        website = request.env['website'].get_current_website()
        if http.request.httprequest.method == 'POST':
            required_fields = ['name', 'email', 'app', 'reason']
            missing = [f for f in required_fields if not post.get(f)]
            if missing:
                error = f'Faltan campos: {", ".join(missing)}'
                return http.request.render('pagoflex_integration_bdc.account_close_form', {'error': error, 'website': website})
            else:
                http.request.env['pagoflex.account.close'].sudo().create({
                    'name': post['name'],
                    'email': post['email'],
                    'app': post['app'],
                    'reason': post['reason'],
                })
                return http.request.render('pagoflex_integration_bdc.account_close_success', {'website': website})
        else:
            error = None
        return http.request.render('pagoflex_integration_bdc.account_close_form', {'error': error, 'website': website})
