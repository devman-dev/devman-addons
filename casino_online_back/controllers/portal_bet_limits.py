# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request

class PortalBetLimitsController(http.Controller):

    @http.route('/mi/limites', type='http', auth='user', website=True)
    def portal_bet_limits(self, **kw):
        partner = request.env.user.partner_id
        company = request.env.company
        bl = request.env['bet.limits'].sudo().get_or_create_for_partner(partner, company)
        # Si quisieras inicializar mensajes por defecto, podrías hacer un write aquí si están vacíos
        return request.render('casino_online_back.portal_bet_limits_form', {'bl': bl})

    @http.route('/mi/limites/casino/bet_limits/save', type='http', auth='user', website=True, methods=['POST'])
    def portal_bet_limits_save(self, **post):
        partner = request.env.user.partner_id
        company = request.env.company
        env = request.env['bet.limits'].sudo()
        bl = env.get_or_create_for_partner(partner, company)

        # Sanitizar y asegurar no-negativos
        def f(v): 
            try:
                x = float(v or 0)
                return x if x >= 0 else 0.0
            except Exception:
                return 0.0

        vals = {
            'limit_daily': f(post.get('limit_daily')),
            'limit_weekly': f(post.get('limit_weekly')),
            'limit_monthly': f(post.get('limit_monthly')),
        }
        # (opcional) validar business rules extra aquí
        bl.write(vals)

        # redirigí a la vista con un query param si querés mostrar toast de éxito
        return request.redirect('/mi/limites?_saved=1')
