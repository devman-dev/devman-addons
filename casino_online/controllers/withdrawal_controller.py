from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied
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
    
    @http.route('/casino/withdrawal/validate_password', type='json', auth='user', website=True)
    def validate_password(self, password, **kw):
        """
        Valida la contraseña del usuario actual comparando hashes directamente.
        Esto evita errores con _check_credentials en Odoo 18.
        """
        try:
            user = request.env.user.sudo()
            
            # 1. Obtenemos el hash almacenado directamente de la BD
            # Usamos SQL directo para garantizar que leemos el campo 'password' real
            # (El ORM a veces oculta este campo o devuelve False por seguridad)
            request.env.cr.execute(
                "SELECT password FROM res_users WHERE id=%s", 
                (user.id,)
            )
            row = request.env.cr.fetchone()
            
            if not row or not row[0]:
                return {
                    'success': False, 
                    'message': 'Su usuario no tiene una contraseña local configurada.'
                }
            
            stored_hash = row[0]

            # 2. Verificar la contraseña usando la librería criptográfica de Odoo
            try:
                valid = user._crypt_context().verify(password, stored_hash)
            except ValueError:
                # Si el hash en la BD tiene un formato extraño
                return {'success': False, 'message': 'Error en el formato de credenciales.'}

            if valid:
                return {'success': True, 'message': 'Contraseña correcta'}
            else:
                return {'success': False, 'message': 'La contraseña ingresada es incorrecta.'}

        except Exception as e:
            _logger.error(f"Error validando pass: {e}")
            return {
                'success': False, 
                'message': 'Error técnico al validar la contraseña.'
            }
    
    @http.route('/casino/withdrawal/form', type='http', auth='user', website=True)
    def withdrawal_form(self, **kw):
        user = request.env.user
        partner = user.partner_id
        _logger.info("/casino/withdrawal/form --- Accediendo al formulario de retiro para el partner: %s", partner.id)
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
        _logger.info("/mi/retiros --- Accediendo a la página de retiros")
        user = request.env.user
        partner = user.partner_id
        _logger.info("/mi/retiros --- Accediendo a la página de retiros para el partner: %s", partner.id)
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
