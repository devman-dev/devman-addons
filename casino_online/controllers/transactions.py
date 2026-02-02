# controllers/transactions.py
import json
import logging
import math
import urllib
from psycopg2 import IntegrityError
from datetime import date, datetime
from odoo.tools.float_utils import float_round

import werkzeug
from requests import post

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers.portal import PaymentPortal
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


def _serialize_game_session(session):
    if not session:
        return False
    return {
        'id': session.id,
        'game': session.game_id.display_name or session.game_id.name or '',
        'end_round': bool(session.end_round),
        'round_id': session.round_id or '',
        'transaction_id': session.transaction_id or '',
        'amount': float(session.amount or 0.0),
        'event_id': session.event_id or '',
        'event_date': fields.Datetime.to_string(session.event_date) if session.event_date else '',
        'market_id': session.market_id or '',
        'start': fields.Datetime.to_string(session.start) if session.start else '',
    }

class CasinoHome(CustomerPortal):
    @http.route(['/my', '/my/home'], type='http', auth='user', website=True)
    def home(self, **kw):
        res = super().home(**kw)
        partner_sudo = request.env.user.partner_id.sudo()
        res.qcontext['partner_sudo'] = partner_sudo
        _logger.warning("Entered custom home method with kw: %s", res.qcontext)
        
        # values = self._prepare_portal_layout_values()
        values = res.qcontext

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

        # Construir dominio base: partner + company + estado
        account_types = ['asset_receivable', 'liability_payable']
        base_domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', account_types),
            ('parent_state', 'in', ['draft', 'posted', 'in_process']),
        ]

        # Filtrar solo movimientos del journal de custodia si está configurado
        # if company.casino_custodia_journal_id:
        #     base_domain.append(('move_id.journal_id', '=', company.casino_custodia_journal_id.id))

        # Incluir también las líneas asociadas al diario de transferencia del casino
        # (company.casino_deposit_journal_id) si está configurado.
        # Usamos un OR ('|') entre la condición de diario y la de tipo de cuenta.
        # if company.casino_deposit_journal_id:
        #     base_domain += [
        #         '|',
        #         ('move_id.journal_id', '=', company.casino_deposit_journal_id.id),
        #         ('account_id.account_type', 'in', account_types),
        #     ]
        # else:
        #     base_domain += [
        #         ('account_id.account_type', 'in', account_types),
        #     ]

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

        def _eff_create_date(l):
            # prioridad: línea.date, si no existe usar fecha del asiento
            return l.create_date or l.move_id.create_date or date.min

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
            session = l.move_id.game_session_id if l.move_id else False

            iso_date = _eff_create_date(l).isoformat()
            date_obj = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%d-%m-%Y %H:%M')
            _logger.info("Fecha formateada Transaction.py: %s", formatted_date)
            prepared.append({
                'id': l.id,
                'date': formatted_date, #_eff_date(l).isoformat(),
                'description': l.name or l.move_id.ref or l.move_id.name or 'Movimiento contable',
                'type_display': label,
                'type_key': key,
                'amount': round(float(amt or 0.0), 2),
                'state': l.parent_state or l.move_id.state or '',
                'session': _serialize_game_session(session),
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
        company = partner.company_id
        Bet = request.env['casino.game.bet.limits'].sudo()

        bl = Bet.search([('partner_id', '=', partner.id),
                 ('company_id', '=', company.id)], limit=1)
        _logger.info("Bet limits found: %s con partner %s y company %s", bl, partner.id, company.id)
        if not bl:
            _logger.info("Creating default Bet limits for partner %s and company %s", partner.id, company.id)
            bl = Bet.create({
                'partner_id': partner.id,
                'company_id': company.id,
                'limit_daily': 0.0,
                'limit_weekly': 0.0,
                'limit_monthly': 0.0,
            })

        limit_daily   = bl.limit_daily   or 0.0
        limit_weekly  = bl.limit_weekly  or 0.0
        limit_monthly = bl.limit_monthly or 0.0
        _logger.info("Bet limits for partner %s: daily %s, weekly %s, monthly %s", partner.id, limit_daily, limit_weekly, limit_monthly)
        # daily_limit = partner.daily_deposit_limit
        # weekly_limit = partner.weekly_deposit_limit
        # monthly_limit = partner.monthly_deposit_limit

        # Mis Datos Bancarios
        account_number = partner.account_number
        bank_name = partner.bank_name
        account_type = partner.account_type
        cbu = partner.cbu
        cuil = partner.cuil
        nuevo_cbu = partner.nuevo_cbu
        nickname = partner.nickname if partner.nickname else partner.name

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
            'bl': bl,
            # 'limit_daily': limit_daily,
            # 'limit_weekly': limit_weekly,
            # 'limit_monthly': limit_monthly,

            'account_number': account_number,
            'bank_name': bank_name,
            'account_type': account_type,
            'cbu': cbu,
            'cuil': cuil,
            'nuevo_cbu': nuevo_cbu,
            'currency': company.currency_id,
            'nickname': nickname,
        })
        res.qcontext.update(values)
        _logger.info("Rendering portal home for partner %s", values)
        # return request.render("portal.portal_my_home", values)
        return res




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
        _logger.info("PORTAL MOVEMENTS:")
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
            iso_date = dval.isoformat()
            date_obj = datetime.strptime(iso_date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d-%m-%Y')
            _logger.info("Fecha formateada: %s", formatted_date)
            all_movements.append({
                'date': formatted_date,
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

    @http.route('/my/movimientos/data', type='json', auth='user', website=True)
    def portal_movements_data(self, **kwargs):
        args = kwargs or {}
        start_date_s = args.get('start_date') or None
        end_date_s = args.get('end_date') or None
        selected_types = args.get('types') or None
        if isinstance(selected_types, str):
            selected_types = [selected_types]
        if selected_types == []:
            selected_types = None

        start_date = fields.Date.to_date(start_date_s) if start_date_s else None
        end_date = fields.Date.to_date(end_date_s) if end_date_s else None

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

        account_types = ['asset_receivable', 'liability_payable']
        base_domain = [
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('account_id.account_type', 'in', account_types),
            ('parent_state', 'in', ['draft', 'posted', 'in_process']),
        ]

        lines_all = AML.search(base_domain, order='date asc, id asc')

        def _eff_date(line):
            return line.date or line.move_id.date or date.min

        def _eff_create_date(l):
            return l.create_date or l.move_id.create_date or date.min

        if start_date or end_date:
            lines = [line for line in lines_all
                    if (not start_date or _eff_date(line) >= start_date)
                    and (not end_date or _eff_date(line) <= end_date)]
        else:
            lines = list(lines_all)

        def _classify(line):
            mt = line.move_id.move_type or ''
            jn = (line.journal_id and line.journal_id.name or '').lower()
            jt = (line.journal_id.type or '').lower() if line.journal_id else ''
            if any(x in jn for x in ('bonus', 'promo', 'bono')):
                return 'Saldo de Bonus', 'bonus'
            if jt in ('bank', 'cash'):
                return 'Dep./Retiros', 'deposito_retiro'
            if mt in ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'):
                return ('Transacciones de Juegos', 'juego') if 'juego' in jn else ('Facturaci¢n', 'juego')
            if mt == 'entry':
                return 'Ajustes', 'ajuste'
            return 'Ajustes', 'ajuste'

        prepared = []
        selset = set(selected_types) if selected_types else None
        for line in lines:
            label, key = _classify(line)
            if selset and key not in selset:
                continue
            amt = line.amount_signed if line.amount_signed is not None else line.balance
            session = line.move_id.game_session_id if line.move_id else False
            iso_date = _eff_create_date(line).isoformat()
            date_obj = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            formatted_date = date_obj.strftime('%d-%m-%Y %H:%M')
            prepared.append({
                'id': line.id,
                'date': formatted_date,
                'description': line.name or line.move_id.ref or line.move_id.name or 'Movimiento contable',
                'type_display': label,
                'type_key': key,
                'amount': round(float(amt or 0.0), 2),
                'state': line.parent_state or line.move_id.state or '',
                'session': _serialize_game_session(session),
            })

        running = 0.0
        for mv in prepared:
            running += mv['amount']
            mv['balance'] = round(running, 2)

        prepared_desc = list(reversed(prepared))
        total = len(prepared_desc)
        page_count = max(math.ceil(total / page_size), 1)
        if page > page_count:
            page = page_count
        offset = (page - 1) * page_size
        rows = prepared_desc[offset: offset + page_size]

        return {
            'movements': rows,
            'total_movements': total,
            'page': page,
            'page_count': page_count,
            'page_size': page_size,
        }

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
        company = request.env.company
        Bet = request.env['casino.game.bet.limits'].sudo()

        _logger.info("Updating bet limits for partner %s (company %s) with data: %s",
                     partner.id, company.id, post)

        # --- 1) Obtener o crear el registro de límites (concurrencia segura) ---
        bl = Bet.search([('partner_id', '=', partner.id),
                         ('company_id', '=', company.id)], limit=1)
        
        if not bl:
            try:
                with request.env.cr.savepoint():
                    bl = Bet.create({
                        'partner_id': partner.id,
                        'company_id': company.id,
                        'limit_daily': 0.0,
                        'limit_weekly': 0.0,
                        'limit_monthly': 0.0,
                    })
            except IntegrityError:
                # Otra transacción lo creó al mismo tiempo -> recuperar
                request.env.cr.rollback()
                bl = Bet.search([('partner_id', '=', partner.id),
                                 ('company_id', '=', company.id)], limit=1)

        # Seguridad adicional: que el registro corresponda al partner actual
        if not bl or bl.partner_id.id != partner.id:
            _logger.warning("bet.limits not found or not owned by partner %s", partner.id)
            return request.redirect('/my/home#mis_limites_form')
        
        def _num(key):
            """Convierte a float, clamp >= 0 y redondea según la moneda."""
            raw = post.get(key)
            _logger.info("Processing key '%s': raw value = %r (type: %s)", key, raw, type(raw).__name__)
            s = (raw or "").strip()
            # Normaliza separadores: si viene "200,50" (coma decimal) => "200.50"; elimina miles.
            if s:
                if "," in s and "." not in s:
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            try:
                x = float(s or 0.0)
                _logger.info("Float conversion successful: %s -> %f (normalized from %r)", s, x, raw)
            except Exception as e:
                _logger.warning("Failed to parse '%s' (normalized: %s) as float: %s", raw, s, e)
                x = 0.0
            if x < 0:
                _logger.info("Value was negative (%f), clamping to 0", x)
                x = 0.0
            prec = (bl.currency_id.decimal_places or 2) if bl.currency_id else 2
            _logger.info("Using precision: %d digits", prec)
            result = float_round(x, precision_digits=prec)
            _logger.info("After float_round: %s -> %.10f (rounded to %d digits)", key, result, prec)
            return result

        vals = {
            'limit_daily': _num('limit_daily'),
            'limit_weekly': _num('limit_weekly'),
            'limit_monthly': _num('limit_monthly'),
        }

        _logger.info("Writing values to bet_limits record %s: %s", bl.id, vals)
        _logger.info("Before write - current values: daily=%s, weekly=%s, monthly=%s", 
                     bl.limit_daily, bl.limit_weekly, bl.limit_monthly)
        
        # --- 3) Guardar ---
        bl.write(vals)
        
        # Forzar commit y refrescar
        request.env.cr.commit()
        bl.invalidate_recordset()
        
        _logger.info("After write and commit - values: daily=%s, weekly=%s, monthly=%s", 
                     bl.limit_daily, bl.limit_weekly, bl.limit_monthly)
        _logger.info("Successfully updated bet_limits record %s", bl.id)

        # (Opcional) mensaje flash -> podrías usar web.assets/JS para mostrar toast con ?saved=1
        return request.redirect('/my/home#mis_limites_form')
 
    @http.route('/my/mis_limites2', type='http', auth='user', website=True, methods=['GET', 'POST'], csrf=True)
    def portal_mis_limites2(self, **post):
        partner = request.env.user.partner_id.sudo()
        if request.httprequest.method == 'POST':
            vals = {}
            if post.get('limit_daily'):
                vals['daily_deposit_limit'] = float(post.get('limit_daily'))
            if post.get('limit_weekly'):
                vals['weekly_deposit_limit'] = float(post.get('limit_weekly'))
            if post.get('limit_monthly'):
                vals['monthly_deposit_limit'] = float(post.get('limit_monthly'))
            partner.write(vals)
            _logger.info(f"POST Updated limits for partner {partner.id}: {vals}")
            return request.redirect('/my/mis_limites')

        _logger.info(f"GET Render limits for partner {partner.id} \n%s\n%s\n%s", partner.daily_deposit_limit, partner.weekly_deposit_limit, partner.monthly_deposit_limit)
        return request.redirect('/my/movimientos')
        return request.render('casino_online.portal_mis_limites',  {
            'limit_daily': partner.daily_deposit_limit,
            'limit_weekly': partner.weekly_deposit_limit,
            'limit_monthly': partner.monthly_deposit_limit,
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
        withdrawals = request.env["casino.game.withdrawals"].sudo().search(
                [("partner_id", "=", request.env.user.partner_id.id)],
                order="date desc",
                limit=20
            )

        return request.render('casino_online.portal_retirar_form', {'payment_providers': payment_methods, "withdrawals": withdrawals})

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
            ('parent_state', 'in', ['draft1', 'posted']),
        ]
        _logger.info("Search domain for movements balance: %s", domain)
        lines = request.env['account.move.line'].sudo().search(domain)
        _logger.info("Found %d lines for balance calculation", len(lines))
        total_lines = sum(
            float((l.amount_signed if l.amount_signed is not None else l.balance) or 0.0)
            for l in lines
        )

        # Incluir también los pagos (account.payment) que estén en estado 'posted'
        Payment = request.env['account.payment'].sudo()
        payments = Payment.search([
            ('company_id', '=', company.id),
            ('partner_id', '=', partner.id),
            ('state', 'in', ['posted','in_process']),
            ('journal_id', '=', company.casino_deposit_journal_id.id),
        ])
        _logger.info("Found %d payments for balance calculation", len(payments))

        total_payments = 0.0
        for p in payments:
            try:
                amt = float(p.amount or 0.0)
            except Exception:
                amt = 0.0
            pt = getattr(p, 'payment_type', None)
            sign = 0
            if pt == 'inbound':
                sign = 1
            elif pt == 'outbound':
                sign = -1
            elif pt == 'transfer':
                # Si es una transferencia y usa el diario de depósito del casino,
                # considerarlo como entrada (por ejemplo, movimientos internos de casino).
                if company.casino_deposit_journal_id and p.journal_id and p.journal_id.id == company.casino_deposit_journal_id.id:
                    sign = 1
                else:
                    sign = 0
            else:
                sign = 0
            total_payments += sign * amt

        total = total_lines + total_payments
        _logger.info("Total from lines: %s, payments: %s, combined total: %s", total_lines, total_payments, total)
        _logger.info("Total movements balance calculated: %s", total)
        return http.Response(
            json.dumps({'balance': round(total, 2)}),
            content_type='application/json'
        )


class CasinoPaymentPortal(PaymentPortal):
    """
    Heredar PaymentPortal para interceptar la creación de transacciones.
    El balance_game se actualizará cuando la transacción esté confirmada (state='done').
    """

    @http.route('/payment/transaction', type='json', auth='public', website=True)
    def payment_transaction(self, **kwargs):
        """
        Override para crear transacciones de depósito.
        La actualización del balance_game se realiza en el modelo cuando state='done'.
        """
        _logger.info("CasinoPaymentPortal: Intercepting /payment/transaction with kwargs: %s", kwargs)
        
        # Llamar al método original para crear la transacción
        result = super().payment_transaction(**kwargs)
        
        return result
