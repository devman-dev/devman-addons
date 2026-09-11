# -*- coding: utf-8 -*-
#############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Safa KB @ Cybrosys, (odoo@cybrosys.com)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
import logging
import werkzeug
from werkzeug.urls import url_encode
from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.addons.web.controllers.home import ensure_db, Home, \
    SIGN_UP_REQUEST_PARAMS, LOGIN_SUCCESSFUL_PARAMS

_logger = logging.getLogger(__name__)
LOGIN_SUCCESSFUL_PARAMS.add('account_created')


class AuthSignupHome(Home):
    """Portal user login"""
    @http.route()
    def web_login(self, *args, **kw):
        """Function have login features"""
        response = super().web_login(*args, **kw)
        if response.qcontext and response.qcontext.get('login', False):
            inactive_user = request.env['res.users.approve'].sudo().search(
                [('email', '=', response.qcontext.get('login')),
                 ('for_approval_menu', '=', False)])
            if inactive_user:
                response.qcontext["error"] = _(
                    "You can login only after your login get approved..!")
        return response

    @http.route('/web/signup', type='http', auth='public', website=True,
                sitemap=False)
    def web_auth_signup(self, *args, **kw):
        """Function have signup features"""
        qcontext = self.get_auth_signup_qcontext()
        values = {k: v for k, v in request.params.items() if
                  k in SIGN_UP_REQUEST_PARAMS}
        signup_approval = request.env['ir.config_parameter'].sudo().get_param(
            'website_signup_approval.auth_signup_approval')
        if values:
            if signup_approval:
                return request.redirect('/success')
        if not qcontext.get('token') and not qcontext.get('signup_enabled'):
            raise werkzeug.exceptions.NotFound()
        if 'error' not in qcontext and request.httprequest.method == 'POST':
            try:
                self.do_signup(qcontext)
                if qcontext.get('token'):
                    user = request.env['res.users']
                    user_sudo = user.sudo().search(
                        user._get_login_domain(qcontext.get('login')),
                        order=user._get_login_order(), limit=1
                    )
                    template = request.env.ref(
                        'auth_signup.mail_template_user_signup_account_created',
                        raise_if_not_found=False)
                    if user_sudo and template:
                        template.sudo().send_mail(user_sudo.id,
                                                  force_send=True)
                return self.web_login(*args, **kw)
            except UserError as e:
                qcontext['error'] = e.args[0]
            except (SignupError, AssertionError) as e:
                if request.env["res.users"].sudo().search(
                        [("login", "=", qcontext.get("login"))]):
                    qcontext["error"] = _(
                        "Another user is already registered using this email "
                        "address.")
                else:
                    _logger.error("%s", e)
                    qcontext['error'] = _("Could not create a new account.")
        elif 'signup_email' in qcontext:
            user = request.env['res.users'].sudo().search(
                [('email', '=', qcontext.get('signup_email')),
                 ('state', '!=', 'new')], limit=1)
            if user:
                return request.redirect('/web/login?%s' % url_encode(
                    {'login': user.login, 'redirect': '/web'}))
        response = request.render('auth_signup.signup', qcontext)
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "frame-ancestors 'self'"
        return response

    @http.route('/success', type='http', auth='public', website=True,
                sitemap=False)
    def approval_success(self):
        """Create approval request success form"""
        return request.render("website_signup_approval.approval_form_success")


class SignUpApproveController(http.Controller):
    """Manage Approval Request in Backend"""
    @http.route(['/web/signup/approve'], type='json', auth='public')
    def create_attachment(self, **dat):
        """Create approval request and attachment in backend"""
        data_list = []
        for data in dat['data']:
            data = data.split('base64')[1] if data else False
            data_list.append((0, 0, {'attachments': data}))
        if request.env['res.users.approve'].sudo().search(
                [('email', '=', dat['email'])]):
            pass
        else:
            attach = request.env['res.users.approve'].sudo().create(
                {'name': dat['username'],
                 'email': dat['email'],
                 'password': dat['password'],
                 'attachment_ids': data_list
                 })
            for data in dat['data']:
                data = data.split('base64')[1] if data else False
                request.env['ir.attachment'].sudo().create(
                    {'name': attach.name,
                     'datas': data,
                     'res_model': 'res.users.approve',
                     'res_id': attach.id,
                     }
                )
        
        auto_approve_param = request.env['ir.config_parameter'].sudo().get_param(
            'website_signup_approval.auto_approve_portal_signup')
        auto_approve_enabled = str(auto_approve_param).lower() == 'true'
        if auto_approve_enabled:
            attach.action_approve_login()
            request.env.cr.commit()
            # Verificar que el usuario fue creado antes de agregar saldo
            user = request.env['res.users'].sudo().search([('email', '=', dat['email'])], limit=1)
            if user:
                self._add_initial_balance(attach)
                login_val = user.login
            else:
                _logger.error(f"Usuario no fue creado después de aprobación para {dat['email']}")
                login_val = dat['email']
            
            return {
                'redirect_url': '/web/login?%s' % url_encode({'login': login_val, 'redirect': '/web'})
            }
        
        # Si no hay auto-aprobación, responder OK para que el front actúe según corresponda
        return {'status': 'ok'}

    def _add_initial_balance(self, approval_record):
        """Agregar saldo inicial de 100000 al usuario aprobado y crear asiento"""
        try:
            from odoo import fields
            from datetime import datetime
            
            # Buscar el usuario creado
            user = request.env['res.users'].sudo().search(
                [('email', '=', approval_record.email)], limit=1)
            if not user:
                _logger.warning(f"No se encontró usuario para email {approval_record.email}")
                return
            
            partner = user.partner_id
            if not partner:
                _logger.warning(f"No se encontró partner para usuario {user.id}")
                return
            
            # Agregar 1000000 de saldo inicial via money.flow
            flow_tx = request.env['casino.money.flow'].sudo().process_operation(
                operation_type='bonus',
                partner_id=partner,
                amount=1000000.00,
                idempotency_key=f"BONUS|{approval_record.id}",
                external_reference=str(approval_record.id),
                origin_model='website.signup.approval',
                origin_id=approval_record.id,
                note=f'Bono de bienvenida para {user.nickname or user.name}',
            )
            _logger.info(f"Saldo inicial agregado al usuario {user.id}: 1000000 | flow_tx_id={flow_tx.id} | balance_after={flow_tx.balance_after}")
            
            # Crear asiento contable de depósito inicial
            try:
                # Obtener journals custodia y operativa
                operativa_journal = request.env.company.sudo().casino_operativa_journal_id
                if operativa_journal and operativa_journal.default_account_id:
                    account = operativa_journal.default_account_id
                else:
                    # Fallback a búsqueda por código
                    account = request.env['account.account'].sudo().search([('code', '=', '400001')], limit=1)
                    if not account:
                        # Crear cuenta si no existe
                        account = request.env['account.account'].sudo().create({
                            'name': 'Cuenta Juegos Casino',
                            'code': '400001',
                            'account_type': 'income',
                        })

                custodia_journal = request.env.company.sudo().casino_custodia_journal_id
                if custodia_journal:
                    default_account = custodia_journal.sudo().default_account_id
                    if not default_account:
                        default_account = request.env['account.account'].sudo().search([('code', '=', '110101')], limit=1)
                    
                # Formatear fecha en lenguaje natural
                meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                today = fields.Date.today()
                fecha_formateada = f"En {today.day} de {meses[today.month - 1]}"
                
                # Crear líneas del asiento
                move_lines = [
                    (0, 0, {
                        'name': f'BONO de Bienvenida {user.nickname or user.name}',
                        'account_id': account.id,
                        'partner_id': partner.id,
                        'debit': 0.0,
                        'credit': 1000000.00,
                    }),
                    (0, 0, {
                        'name': f'BONO de Bienvenida {user.nickname or user.name}',
                        'account_id': default_account.id,
                        'partner_id': partner.id,
                        'debit': 1000000.00,
                        'credit': 0.0,
                    }),
                ]
                
                # Crear el asiento
                move_vals = {
                    'move_type': 'entry',
                    'partner_id': partner.id,
                    'name': f'BONO {user.nickname or user.name}',
                    'journal_id': custodia_journal.id,
                    'date': today,
                    'ref': f'BONO {user.nickname or user.name}',
                    'line_ids': move_lines,
                }
                
                move = request.env['account.move'].sudo().create(move_vals)
                
                # Postear el asiento
                if move.state == 'draft':
                    move.action_post()
                    _logger.info(f"Asiento de depósito inicial creado y posteado: {move.id}")
                
            except Exception as e:
                _logger.error(f"Error al crear asiento de depósito inicial: {str(e)}")
                # No bloquear si falla el asiento, ya se actualizó el balance
        
        except Exception as e:
            _logger.error(f"Error al agregar saldo inicial: {str(e)}")