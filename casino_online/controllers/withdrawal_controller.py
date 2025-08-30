from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class CasinoWithdrawalPortal(http.Controller):

    @http.route('/casino/withdrawal/form', type='http', auth='user', website=True)
    def withdrawal_form(self, **kwargs):
        _logger.info("Accediendo al formulario de retiro para el partner: %s", request.env.user.partner_id.id)
        partner = request.env.user.partner_id
        bank_accounts = request.env['res.partner.bank'].sudo().search([('partner_id', '=', partner.id)])
        return request.render("casino_online.portal_retirar_form", {
            'bank_accounts': bank_accounts,
        })
    
    @http.route(['/mi/retiros'], type='http', auth="user", website=True)
    def portal_withdrawals(self, **kwargs):
        _logger.info("Accediendo a la página de retiros")
        user = request.env.user
        partner = user.partner_id
        _logger.info("Accediendo a la página de retiros para el partner: %s", partner.id)
        # Bancos asociados al partner
        bank_accounts = request.env["casino.game.bank"].sudo().search([
            ("partner_id", "=", partner.id)
        ])

        # Últimos retiros del partner
        withdrawals = request.env["casino.game.withdrawals"].sudo().search(
            [("partner_id", "=", partner.id)],
            order="date desc",
            limit=20
        )

        values = {
            "bank_accounts": bank_accounts,
            "withdrawals": withdrawals,
        }
        return request.render("casino_online.portal_retirar_form", values)
