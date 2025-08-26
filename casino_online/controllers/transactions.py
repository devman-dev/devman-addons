# controllers/transactions.py
import json
import logging
import math
import urllib
from datetime import date, datetime

import werkzeug
from requests import post

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers.portal import PaymentPortal
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)

class CasinoHome(CustomerPortal):
    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        values = self._prepare_portal_layout_values()

        # === usar MultiDict para soportar getlist ===
        args = request.httprequest.args
        start_date_s   = args.get('start_date') or None
        end_date_s     = args.get('end_date') or None
        selected_types = args.getlist('types') or None

        # parse robusto
        start_date = fields.Date.to_date(start_date_s) if start_date_s else None
        end_date   = fields.Date.to_date(end_date_s) if end_date_s else None

        try:
            page = max(int(args.get('page', 1)), 1)
        except Exception:
            page = 1
        try:
            page_size = min(max(int(args.get('page_size', 10)), 1), 100)
        except Exception:
            page_size = 10

        partner = request.env.user.partner_id.commercial_partner_id
        company = request.env.company
        AML = request.env['account.move.line'].sudo()

        base_domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', 'in', ['draft', 'posted']),
        ]

        # ================================
        # ANTES
        # ================================
        # start_date = _parse_date(kw.get('start_date'))
        # end_date = _parse_date(kw.get('end_date'))
        # filtered = bool(start_date or end_date)
        #
        # if filtered:
        #     domain_display = list(base_domain)
        #     if start_date:
        #         domain_display.append(('date', '>=', start_date))
        #     if end_date:
        #         domain_display.append(('date', '<=', end_date))
        #     lines_display = AML.search(domain_display, order='date asc, id asc')
        # else:
        #     # últimos 10
        #     last10 = AML.search(base_domain, order='date desc, id desc', limit=10)
        #     lines_display = last10.sorted(key=lambda r: (r.date or date.min, r.id))
        #
        # → Problema: cuando filtrabas se mostraban todos juntos,
        #   sin paginación, y por defecto solo 10.

        # ================================
        # AHORA (versión corregida con paginación)
        # ================================

        # saldo global
        saldo_total = sum(
            float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
            for l in AML.search(base_domain)
        )

        # traigo todas las líneas del partner y filtro por fecha en Python usando fecha efectiva
        lines_all = AML.search(base_domain, order='date asc, id asc')

        def _eff_date(l):
            # prioridad: línea.date, si no existe usar fecha del asiento
            return l.date or l.move_id.date or date.min

        # filtro por fecha si vienen parámetros
        if start_date or end_date:
            lines = [l for l in lines_all
                     if (not start_date or _eff_date(l) >= start_date)
                     and (not end_date or _eff_date(l) <= end_date)]
        else:
            lines = list(lines_all)

        def _classify(l):
            mt = l.move_id.move_type or ''
            jn = (l.journal_id and l.journal_id.name or '').lower()
            jt = (l.journal_id.type or '').lower() if l.journal_id else ''
            if any(x in jn for x in ('bonus', 'promo', 'bono')):
                return 'Saldo de Bonus', 'bonus'
            if jt in ('bank', 'cash'):
                return 'Dep./Retiros', 'deposito_retiro'
            if mt in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                return ('Transacciones de Juegos', 'juego') if 'juego' in jn else ('Facturación', 'juego')
            if mt == 'entry':
                return 'Ajustes', 'ajuste'
            return 'Ajustes', 'ajuste'

        prepared = []
        selset = set(selected_types) if selected_types else None
        for l in lines:
            label, key = _classify(l)
            if selset and key not in selset:
                continue
            amt = l.amount_signed if l.amount_signed is not None else l.balance
            prepared.append({
                'id': l.id,
                'date': _eff_date(l).isoformat(),
                'description': l.name or l.move_id.ref or l.move_id.name or 'Movimiento contable',
                'type_display': label,
                'type_key': key,
                'amount': round(float(amt or 0.0), 2),
                'state': l.parent_state or l.move_id.state or '',
            })

        # saldo progresivo sobre el subconjunto filtrado (ascendente para calcular balance)
        running = 0.0
        for mv in prepared:
            running += mv['amount']
            mv['balance'] = round(running, 2)

        # === ORDENAR Y PAGINAR EN DESCENDENTE (últimos primero) ===
        prepared_desc = list(reversed(prepared))  # respeta el orden original y lo invierte
        total = len(prepared_desc)
        page_count = max(math.ceil(total / page_size), 1)
        if page > page_count:
            page = page_count
        offset = (page - 1) * page_size
        rows = prepared_desc[offset: offset + page_size]

        # Mis Límites
        daily_limit = partner.daily_deposit_limit
        weekly_limit = partner.weekly_deposit_limit
        monthly_limit = partner.monthly_deposit_limit

        # Mis Datos Bancarios
        account_number = partner.account_number
        bank_name = partner.bank_name
        account_type = partner.account_type
        cbu = partner.cbu
        cuil = partner.cuil
        nuevo_cbu = partner.nuevo_cbu
        
        values.update({
            'movements': rows,
            'saldo_final': round(saldo_total, 2),
            'total_movements': total,
            'page': page,
            'page_count': page_count,
            'page_size': page_size,
            'start_date': start_date_s,
            'end_date': end_date_s,
            'selected_types': selected_types,
            'daily_limit': daily_limit,
            'weekly_limit': weekly_limit,
            'monthly_limit': monthly_limit,

            'account_number': account_number,
            'bank_name': bank_name,
            'account_type': account_type,
            'cbu': cbu,
            'cuil': cuil,
            'nuevo_cbu': nuevo_cbu,
            'currency': company.currency_id
        })
        return request.render("portal.portal_my_home", values)




class MiPortalController(http.Controller):

    @http.route('/my/movimientos2', type='http', auth='user', website=True)
    def portal_movimientos2(self, **kwargs):
        movements = [
            {'date': datetime(2025, 8, 5), 'description': 'Depósito inicial', 'type_display': 'Dep./Retiros', 'amount': 1000.00, 'state': 'Completado', 'balance': 1000.00},
            {'date': datetime(2025, 8, 6), 'description': 'Retiro cajero', 'type_display': 'Dep./Retiros', 'amount': -200.00, 'state': 'Pendiente', 'balance': 800.00},
            {'date': datetime(2025, 8, 7), 'description': 'Bonus por promoción', 'type_display': 'Saldo de Bonus', 'amount': 50.00, 'state': 'Completado', 'balance': 850.00},
            {'date': datetime(2025, 8, 8), 'description': 'Transacción juego A', 'type_display': 'Transacciones de Juegos', 'amount': -30.00, 'state': 'Completado', 'balance': 820.00},
            {'date': datetime(2025, 8, 9), 'description': 'Ajuste manual', 'type_display': 'Ajustes', 'amount': 10.00, 'state': 'Completado', 'balance': 830.00},
        ]
        return request.render('casino_online.portal_movimientos', {
            'movements': movements,
            'request': request,
        })

    # Puedes dejar esto o eliminarlo. El form ya no lo usa.
    @http.route('/my/movimientos', type='http', auth='user', website=True)
    def portal_movements(self, **kwargs):
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.env.company
        domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', 'in', ['draft', 'posted']),
        ]
        lines = request.env['account.move.line'].sudo().search(domain, order='date asc, id asc')

        def classify_line(l):
            mt = l.move_id.move_type or ''
            jn = (l.journal_id and l.journal_id.name or '').lower()
            if any(x in jn for x in ('bonus', 'promo', 'bono')):
                return 'Saldo de Bonus'
            if mt in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                return 'Transacciones de Juegos' if 'juego' in jn else 'Facturación'
            if mt == 'entry':
                return 'Ajustes'
            return 'Ajustes'

        def describe_line(l):
            return l.name or l.move_id.ref or l.move_id.name or 'Movimiento contable'

        all_movements = []
        for l in lines:
            dval = l.date
            amt = l.amount_signed if l.amount_signed is not None else l.balance
            all_movements.append({
                'date': dval.isoformat(),
                'datetime_obj': dval or datetime.min,
                'description': describe_line(l),
                'type_display': classify_line(l),
                'amount': round(float(amt or 0.0), 2),
                'state': l.parent_state or l.move_id.state or '',
            })

        all_movements.sort(key=lambda x: x['datetime_obj'])
        balance = 0.0
        for mv in all_movements:
            balance += mv['amount']
            mv['balance'] = round(balance, 2)
            mv.pop('datetime_obj', None)

        ctx = {
            'movements': all_movements,
            'saldo_final': round(balance, 2),
            'total_movements': len(all_movements),
            'request': request,
        }
        return request.render('casino_online.portal_movimientos', ctx)

    @http.route('/mi-cuenta/movimientos', type='http', auth='user', website=True)
    def portal_movements_alias(self, **kw):
        qs = request.httprequest.query_string.decode() or ''
        return request.redirect('/my/movimientos' + (f'?{qs}' if qs else ''))

    # Resto de endpoints existentes (sin cambios)
    @http.route('/my/medios_pagos', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_medios_pagos(self, **post):
        partner = request.env.user.partner_id
        PaymentProvider = request.env['payment.provider']
        ConfigModel = request.env['partner.payment.method.config'].sudo()

        if request.httprequest.method == 'POST':
            payment_methods = PaymentProvider.sudo().search([('state', '=', 'enabled')])
            for pm in payment_methods:
                for_deposit = bool(post.get(f'deposit_{pm.id}'))
                for_withdraw = bool(post.get(f'withdraw_{pm.id}'))
                config = ConfigModel.search([('partner_id', '=', partner.id), ('payment_provider_id', '=', pm.id)], limit=1)
                vals = {'for_deposit': for_deposit, 'for_withdraw': for_withdraw}
                if config:
                    config.write(vals)
                else:
                    vals.update({'partner_id': partner.id, 'payment_provider_id': pm.id})
                    ConfigModel.create(vals)
            return request.redirect('/my/medios_pagos')

        payment_methods = PaymentProvider.sudo().search([('state', '=', 'enabled')])
        for pm in payment_methods:
            pm.config = ConfigModel.search([('partner_id', '=', partner.id), ('payment_provider_id', '=', pm.id)], limit=1)

        return request.render('casino_online.portal_medios_pagos', {'payment_methods': payment_methods})

    @http.route('/my/mis_limites', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def portal_mis_limites(self, **post):
        partner = request.env.user.partner_id
        partner.write({
            'daily_deposit_limit': post.get('daily_limit'),
            'weekly_deposit_limit': post.get('weekly_limit'),
            'monthly_deposit_limit': post.get('monthly_limit'),
        })

        return request.redirect('/my/home#mis_limites_form')

    @http.route('/my/mis_limites2', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_mis_limites2(self, **post):
        partner = request.env.user.partner_id.sudo()
        if request.httprequest.method == 'POST':
            vals = {}
            if post.get('daily_limit'):
                vals['daily_deposit_limit'] = float(post.get('daily_limit'))
            if post.get('weekly_limit'):
                vals['weekly_deposit_limit'] = float(post.get('weekly_limit'))
            if post.get('monthly_limit'):
                vals['monthly_deposit_limit'] = float(post.get('monthly_limit'))
            partner.write(vals)
            _logger.info(f"POST Updated limits for partner {partner.id}: {vals}")
            return request.redirect('/my/mis_limites')

        _logger.info(f"GET Render limits for partner {partner.id} \n%s\n%s\n%s", partner.daily_deposit_limit, partner.weekly_deposit_limit, partner.monthly_deposit_limit)
        return request.redirect('/my/movimientos')
        return request.render('casino_online.portal_mis_limites',  {
            'daily_limit': partner.daily_deposit_limit,
            'weekly_limit': partner.weekly_deposit_limit,
            'monthly_limit': partner.monthly_deposit_limit,
        })
        # return request.redirect('/my/movimientos' + (f'?{qs}' if qs else ''))   

    @http.route('/my/datos_bank', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_datos_bancarios(self, **post):
        partner = request.env.user.partner_id.sudo()
        if request.httprequest.method == 'POST':
            vals = {
                'account_number': post.get('account_number'),
                'bank_name': post.get('bank_name'),
                'account_type': post.get('account_type'),
                'cbu': post.get('cbu'),
                'cuil': post.get('cuil'),
                'nuevo_cbu': post.get('nuevo_cbu'),
            }
            partner.write(vals)
            return request.redirect('/my/home#datos_bank')

        return request.render('casino_online.portal_datos_bancarios', {
            'account_number': partner.account_number,
            'bank_name': partner.bank_name,
            'account_type': partner.account_type,
            'cbu': partner.cbu,
            'cuil': partner.cuil,
            'nuevo_cbu': partner.nuevo_cbu,
        })

    @http.route('/my/depositar', type='http', auth='user', website=True, methods=["GET", "POST"], crsf=True)
    def depositar_form(self, amount=False, currency_id=False, partner_id=False, company_id=False, access_token=False, **kwargs):
        PaymentProvider = request.env["payment.provider"].sudo()
        PaymentMethod = request.env["payment.method"].sudo()
        PaymentToken = request.env["payment.token"].sudo()
        ResCurrency = request.env["res.currency"].sudo()
        ResCompany = request.env["res.company"].sudo()
        ResPartner = request.env["res.partner"].sudo()

        currency_id, partner_id, company_id = tuple(
            map(
                PaymentPortal._cast_as_int,
                (currency_id, partner_id, company_id),
            ),
        )
        amount = PaymentPortal._cast_as_float(amount)

        if partner_id:
            if not payment_utils.check_access_token(access_token, partner_id, amount, currency_id):
                raise werkzeug.exceptions.NotFound()

        user_sudo = request.env.user
        logged_in = not user_sudo._is_public()

        partner_is_different = False
        if logged_in:
            partner_is_different = partner_id and partner_id != user_sudo.partner_id.id
            partner_sudo = user_sudo.partner_id
        else:
            partner_sudo = ResPartner.browse(partner_id).exists()
            if not partner_sudo:
                return request.redirect(
                    f"/web/login?redirect={urllib.parse.quote(request.httprequest.full_path)}"
                )

        amount = amount or 10.0
        company_id = company_id or partner_sudo.company_id.id or user_sudo.company_id.id
        company = ResCompany.browse(company_id)
        currency_id = currency_id or company.currency_id.id

        currency = ResCurrency.browse(currency_id).exists()
        if not currency or not currency.active:
            raise werkzeug.exceptions.NotFound()

        availability_report = {}

        # Obtener proveedores compatibles con manejo seguro
        providers_sudo = PaymentProvider._get_compatible_providers(
            company_id,
            partner_sudo.id,
            amount,
            currency_id=currency.id,
            report=availability_report,
            **kwargs,
        )
        # Obtener métodos de pago con manejo seguro
        payment_methods_sudo = PaymentMethod._get_compatible_payment_methods(
            providers_sudo.ids,
            partner_sudo.id,
            currency_id=currency.id,
            report=availability_report,
        )
        # Obtener tokens con manejo seguro
        tokens_sudo = PaymentToken._get_available_tokens(providers_sudo.ids, partner_sudo.id)

        company_mismatch = not PaymentPortal._can_partner_pay_in_company(partner_sudo, company)
        access_token = payment_utils.generate_access_token(partner_sudo.id, amount, currency.id)

        portal_page_values = {
            "res_company": company,
            "company_mismatch": company_mismatch,
            "expected_company": company,
            "partner_is_different": partner_is_different,
        }
        payment_form_values = {
            "show_tokenize_input_mapping": PaymentPortal._compute_show_tokenize_input_mapping(
                providers_sudo,
                **kwargs,
            )
        }
        payment_context = {
            "reference_prefix": payment_utils.singularize_reference_prefix(prefix="DEP"),
            "amount": amount,
            "currency": currency,
            "partner_id": partner_sudo.id,
            "providers_sudo": providers_sudo,
            "payment_methods_sudo": payment_methods_sudo,
            "tokens_sudo": tokens_sudo,
            "availability_report": availability_report,
            "transaction_route": "/payment/transaction",
            "landing_route": "/payment/confirmation",
            "access_token": access_token
        }

        rendering_context = {
            **portal_page_values,
            **payment_form_values,
            **payment_context,
            "display_submit_button": False
            # **PaymentPortal._get_extra_payment_form_values(
            #     **payment_context,
            #     currency_id=currency.id,
            #     **kwargs,
            # ),
        }

        return request.render("casino_online.portal_depositar_form", rendering_context)

    @http.route('/my/retirar', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_retirar(self, **post):
        if http.request.httprequest.method == 'POST':
            amount = post.get('amount')
            payment_provider_id = post.get('payment_provider_id')
            if not amount or not payment_provider_id:
                return request.redirect('/my/retirar')
            request.env['portal.retiro'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'amount': float(amount),
                'payment_provider_id': int(payment_provider_id),
            })
            return request.redirect('/my')

        payment_methods = request.env['payment.provider'].sudo().search([
            ('state', '=', 'test'), ('is_published', '=', True)
        ])
        return request.render('casino_online.portal_retirar_form', {'payment_providers': payment_methods})

    @http.route('/my/registrar_bonus', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_registrar_bonus(self, **post):
        if request.httprequest.method == 'POST':
            promo_code = post.get('promo_code')
            if not promo_code:
                return request.redirect('/my/registrar_bonus')
            request.env['portal.bonus'].sudo().create({
                'partner_id': request.env.user.partner_id.id,
                'code': promo_code,
            })
            return request.redirect('/my')

        return request.render('casino_online.portal_registrar_bonus_form')

    @http.route('/my/movimientos/balance', type='http', auth='public', website=True, methods=['GET', 'POST'], csrf=False)
    def get_movements_balance(self, **kwargs):
        _logger.info("Calculating movements balance for user %s", request.env.user.partner_id.name)
        partner = request.env.user.partner_id.commercial_partner_id
        company = request.env.company
        token = kwargs.get('token')
        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
        _logger.info("Partner found: %s, token: %s", partner.name if partner else 'None', token)

        domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('parent_state', 'in', ['draft', 'posted']),
        ]
        _logger.info("Search domain for movements balance: %s", domain)
        lines = request.env['account.move.line'].sudo().search(domain)
        _logger.info("Found %d lines for balance calculation", len(lines))
        total = sum(
            float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
            for l in lines
        )
        _logger.info("Total movements balance calculated: %s", total)
        return http.Response(
            json.dumps({'balance': round(total, 2)}),
            content_type='application/json'
        )


        