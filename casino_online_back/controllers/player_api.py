# -*- coding: utf-8 -*-
"""casino_online_back/controllers/player_api.py
JSON endpoints unificados para el Player Frontend.

Endpoints:
  GET /casino/games        → lista de juegos (product.template con is_game=True)
  GET /casino/balance      → saldo real del jugador autenticado
  GET /casino/profile      → perfil JSON unificado (partner + wallet + banks + límites)
  GET /casino/perfil       → página HTML independiente del perfil del jugador
  GET /casino/transactions → historial de transacciones del wallet
"""
import logging
import math
import os
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class CasinoPlayerAPI(http.Controller):

    # ------------------------------------------------------------------
    # 1. Listar juegos
    # ------------------------------------------------------------------
    @http.route('/casino/games', type='json', auth='user', methods=['POST'], csrf=False)
    def list_games(self, **kw):
        """Listar juegos disponibles (product.template con is_game=True, activo).

        Solo jugadores (is_player=True) pueden acceder.
        No modifica el modelo product.template.
        """
        partner = request.env.user.partner_id.sudo()
        if not partner.is_player:
            return {'error': 'El usuario no es jugador', 'games': [], 'total': 0}

        Product = request.env['product.template'].sudo()
        games = Product.search([
            ('is_game', '=', True),
            ('active', '=', True),
            '|',
            ('iframe_url', '!=', False),
            ('provider_id', '!=', False),
        ], order='name')

        result = []
        for game in games:
            result.append({
                'id': game.id,
                'name': game.name or '',
                'code': game.code or '',
                'provider': game.provider_id.name if game.provider_id else '',
                'provider_id': game.provider_id.id if game.provider_id else False,
                'iframe_url': game.iframe_url or '',
                'image_url': f'/web/image/product.template/{game.id}/image_128',
            })

        _logger.info(
            "casino/games → partner_id=%s (%s) — %d games returned",
            partner.id, partner.name, len(result),
        )
        return {'games': result, 'total': len(result)}

    # ------------------------------------------------------------------
    # 2. Saldo real
    # ------------------------------------------------------------------
    @http.route('/casino/balance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_balance(self, **kw):
        """Saldo real del jugador autenticado.

        Fuentes (en orden):
          1. partner.balance_game (fuente de verdad del saldo de juego)
          2. casino.wallet.balance   (espejo, sincronizado por process_operation)

        NO usa account.move.line (balance contable ≠ saldo de juego).
        """
        partner = request.env.user.partner_id.sudo()
        if not partner.is_player:
            return {'error': 'El usuario no es jugador'}

        balance_game = round(float(partner.balance_game or 0.0), 2)
        company = request.env.company

        wallet = request.env['casino.wallet'].sudo().search([
            ('partner_id', '=', partner.id),
            ('wallet_type', '=', 'player'),
            ('company_id', '=', company.id),
        ], limit=1, order='id desc')

        wallet_balance = round(float(wallet.balance or 0.0), 2) if wallet else 0.0
        currency_symbol = company.currency_id.symbol or '$'

        # Límites (sin límite = 0)
        BetLimits = request.env['casino.game.bet.limits'].sudo()
        limits = BetLimits.search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', company.id),
        ], limit=1)

        if limits:
            daily = round(float(limits.limit_daily or 0.0), 2)
            weekly = round(float(limits.limit_weekly or 0.0), 2)
            monthly = round(float(limits.limit_monthly or 0.0), 2)
            spent_daily = round(float(limits.spent_daily or 0.0), 2)
            spent_weekly = round(float(limits.spent_weekly or 0.0), 2)
            spent_monthly = round(float(limits.spent_monthly or 0.0), 2)
        else:
            daily = weekly = monthly = 0.0
            spent_daily = spent_weekly = spent_monthly = 0.0

        _logger.info(
            "casino/balance → partner_id=%s | balance_game=%.2f | wallet=%.2f",
            partner.id, balance_game, wallet_balance,
        )

        return {
            'player_id': partner.id,
            'player_name': partner.name,
            'balance_game': balance_game,
            'wallet_balance': wallet_balance,
            'currency': currency_symbol,
            'wallet_id': wallet.id if wallet else None,
            'limits': {
                'daily':   {'limit': daily,   'spent': spent_daily},
                'weekly':  {'limit': weekly,  'spent': spent_weekly},
                'monthly': {'limit': monthly, 'spent': spent_monthly},
            },
        }

    # ------------------------------------------------------------------
    # 3. Perfil unificado
    # ------------------------------------------------------------------
    @http.route('/casino/profile', type='json', auth='user', methods=['POST'], csrf=False)
    def get_profile(self, **kw):
        """Perfil JSON unificado del jugador autenticado.

        NO expone: password, token, secret_token, ni campos sensibles.
        """
        partner = request.env.user.partner_id.sudo()
        if not partner.is_player:
            return {'error': 'El usuario no es jugador'}

        company = request.env.company

        # --- Datos básicos del partner ---
        profile = {
            'id': partner.id,
            'name': partner.name or '',
            'display_name': partner.display_name or '',
            'email': partner.email or '',
            'phone': partner.phone or '',
            'mobile': partner.mobile or '',
            'image_url': f'/web/image/res.partner/{partner.id}/image_128',
            'is_player': bool(partner.is_player),
            'balance_game': round(float(partner.balance_game or 0.0), 2),

            # Datos bancarios (almacenados en res.partner)
            'bank_name': partner.bank_name or '',
            'account_number': partner.account_number or '',
        }

        # --- Agente asignado (sin token ni datos sensibles) ---
        if partner.agent_id:
            profile['agent'] = {
                'id': partner.agent_id.id,
                'name': partner.agent_id.name or '',
            }
        else:
            profile['agent'] = None

        # --- Wallet ---
        wallet = request.env['casino.wallet'].sudo().search([
            ('partner_id', '=', partner.id),
            ('wallet_type', '=', 'player'),
            ('company_id', '=', company.id),
        ], limit=1, order='id desc')

        if wallet:
            profile['wallet'] = {
                'id': wallet.id,
                'balance': round(float(wallet.balance or 0.0), 2),
                'currency_symbol': wallet.currency_id.symbol or '$',
            }
        else:
            profile['wallet'] = None

        # --- Límites de apuesta ---
        BetLimits = request.env['casino.game.bet.limits'].sudo()
        limits = BetLimits.search([
            ('partner_id', '=', partner.id),
            ('company_id', '=', company.id),
        ], limit=1)

        if limits:
            profile['bet_limits'] = {
                'daily':   {'limit': round(float(limits.limit_daily   or 0.0), 2),
                            'spent': round(float(limits.spent_daily   or 0.0), 2)},
                'weekly':  {'limit': round(float(limits.limit_weekly  or 0.0), 2),
                            'spent': round(float(limits.spent_weekly  or 0.0), 2)},
                'monthly': {'limit': round(float(limits.limit_monthly or 0.0), 2),
                            'spent': round(float(limits.spent_monthly or 0.0), 2)},
            }
        else:
            profile['bet_limits'] = {'daily': {}, 'weekly': {}, 'monthly': {}}

        # --- Bancos del partner (res.partner.bank) ---
        banks = request.env['res.partner.bank'].sudo().search([
            ('partner_id', '=', partner.id),
        ])
        profile['banks'] = [{
            'id': b.id,
            'bank_name': b.bank_id.name if b.bank_id else (b.bank_name or ''),
            'acc_number': b.acc_number or '',
            'acc_type': b.acc_type or '',
        } for b in banks]

        _logger.info(
            "casino/profile → partner_id=%s (%s) | balance=%.2f | banks=%d",
            partner.id, partner.name, profile['balance_game'], len(profile['banks']),
        )

        return profile

    # ------------------------------------------------------------------
    # 4. Página de perfil (HTML independiente)
    # ------------------------------------------------------------------
    @http.route('/casino/perfil', type='http', auth='user')
    def casino_perfil_page(self, **kw):
        """Servir la página profile.html independiente en /casino/perfil.

        Requiere sesión Odoo activa (auth='user').
        No envuelve la página en layout de Odoo — se entrega como HTML standalone.
        """
        addon_path = os.path.dirname(os.path.dirname(__file__))
        html_path = os.path.join(addon_path, 'static', 'src', 'profile.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return request.make_response(html, [
            ('Content-Type', 'text/html; charset=utf-8'),
        ])

    # ------------------------------------------------------------------
    # 4bis. shared.js (JS compartido para todas las vistas standalone)
    # ------------------------------------------------------------------
    @http.route('/casino/shared.js', type='http', auth='public')
    def casino_shared_js(self, **kw):
        addon_path = os.path.dirname(os.path.dirname(__file__))
        js_path = os.path.join(addon_path, 'static', 'src', 'shared.js')
        with open(js_path, 'r', encoding='utf-8') as f:
            js = f.read()
        return request.make_response(js, [
            ('Content-Type', 'application/javascript; charset=utf-8'),
            ('Cache-Control', 'public, max-age=3600'),
        ])

    # ------------------------------------------------------------------
    # 5. Transacciones del wallet del casino
    # ------------------------------------------------------------------
    @http.route('/casino/transactions', type='json', auth='user', methods=['POST'], csrf=False)
    def list_transactions(self, **kw):
        """Listar transacciones del wallet del casino del jugador autenticado.

        Fuente: casino.wallet.transaction (NO account.move.line).
        Solo devuelve transacciones del partner autenticado.
        NO acepta player_id del frontend.
        """
        partner = request.env.user.partner_id.sudo()
        if not partner.is_player:
            return {'error': 'El usuario no es jugador', 'transactions': [], 'total': 0}

        page = max(int(kw.get('page', 1)), 1)
        page_size = min(max(int(kw.get('page_size', 20)), 1), 100)

        WalletTx = request.env['casino.wallet.transaction'].sudo()
        domain = [('partner_id', '=', partner.id)]
        type_filter = kw.get('type', '').strip()
        if type_filter:
            if type_filter == 'deposito_retiro':
                domain += [('transaction_type', 'in', ['deposit', 'withdrawal'])]
            else:
                domain += [('transaction_type', '=', type_filter)]

        total = WalletTx.search_count(domain)
        offset = (page - 1) * page_size

        txns = WalletTx.search(
            domain,
            order='create_date desc, id desc',
            limit=page_size,
            offset=offset,
        )

        result = []
        for tx in txns:
            result.append({
                'id': tx.id,
                'date': str(tx.create_date) if tx.create_date else '',
                'type': tx.transaction_type or '',
                'direction': tx.direction or '',
                'description': tx.name or tx.note or '',
                'amount': round(float(tx.amount or 0.0), 2),
                'balance_before': round(float(tx.balance_before or 0.0), 2),
                'balance_after': round(float(tx.balance_after or 0.0), 2),
                'state': tx.state or '',
            })

        _logger.info(
            "casino/transactions → partner_id=%s | total=%d | page=%d/%d",
            partner.id, total, page, math.ceil(total / page_size) if page_size > 0 else 1,
        )

        return {
            'transactions': result,
            'total': total,
            'page': page,
            'page_count': math.ceil(total / page_size) if page_size > 0 else 1,
        }