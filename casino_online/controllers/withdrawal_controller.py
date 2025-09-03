from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class CasinoWithdrawalPortal(http.Controller):

    @http.route('/casino/withdrawal/banks', type='json', auth='user', website=True)
    def get_partner_banks(self):
        user = request.env.user
        partner = user.partner_id
        banks = request.env['casino.game.bank'].sudo().search([('partner_id', '=', partner.id)])
        return [
            {'id': bank.id, 'name': bank.bank_name, 'cbu': bank.cbu}
            for bank in banks
        ]
    
    @http.route('/casino/withdrawal/form', type='http', auth='user', website=True)
    def withdrawal_form(self, **kw):
        user = request.env.user
        partner = user.partner_id
        _logger.info("PABLO --- /casino/withdrawal/form --- Accediendo al formulario de retiro para el partner: %s", partner.id)
        # buscamos las cuentas bancarias asociadas al partner
        bank_accounts = request.env['casino.game.bank'].sudo().search([
            ('partner_id', '=', partner.id)
        ])

        # renderizamos el template pasando los bancos
        return request.render('casino_online.portal_retirar_form', {
            'withdrawals': request.env['casino.game.withdrawals'].sudo().search(
                [('partner_id', '=', partner.id)], order="date desc", limit=10
            ),
            'bank_accounts': bank_accounts,
            'user_id': user,
        })
    
    @http.route(['/mi/retiros'], type='http', auth="user", website=True)
    def portal_withdrawals(self, **kwargs):
        _logger.info("PABLO --- /mi/retiros --- Accediendo a la página de retiros")
        user = request.env.user
        partner = user.partner_id
        _logger.info("PABLO --- /mi/retiros --- Accediendo a la página de retiros para el partner: %s", partner.id)
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
