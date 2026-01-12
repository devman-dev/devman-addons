from datetime import timedelta, datetime
import token

import requests
from odoo import http, fields
from odoo.http import request, route, Response
import logging
import time
import uuid
import json

_logger = logging.getLogger(__name__)
class CasinoError(Exception):
    def __init__(self, code, message, http_status=400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_dict(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                # "http_status": self.http_status
            }
        }

class CasinoErrorCodes:
    INSUFFICIENT_FUNDS = (1, "Not enough money on player’s wallet", 402)
    AUTHORIZATION_FAILED = (2, "Authorization header is wrong", 401)
    TOKEN_EXPIRED = (3, "Token session is expired", 403)
    UNKNOWN_TRANSACTION_ID = (4, "Transaction ID is unknown", 404)
    INVALID_GAME = (5, "Invalid game", 405)
    INVALID_AMOUNT = (6, "Invalid amount", 406)
    INVALID_TOKEN = (7, "Invalid token", 407)
    TRANSACTION_ALREADY_SETTLED = (8, "Transaction has already been settled", 408)
    DEBIT_TRANSACTION_DOES_NOT_EXIST = (9, "Debit transaction does not exist", 409)
    INVALID_PARAMETER = (400, "Invalid parameter", 400)
    GENERIC_ERROR = (900, "An unexpected error occurred", 900)

def error_response(error: CasinoError):
    return Response(json.dumps(error.to_dict()), content_type='application/json', status=error.http_status)
class GameController(http.Controller):
    def _raise_casino_error(self, code_tuple_or_code, override_msg=None):
        """
        Lanza CasinoError reemplazando el mensaje del tuple si corresponde.
        Soporta tuplas (code, msg) y (code, msg, http_status) o un code suelto.
        """
        ct = code_tuple_or_code
        if isinstance(ct, tuple):
            if len(ct) == 3:
                code, _msg, status = ct
                raise CasinoError(code, override_msg or _msg, status)
            elif len(ct) == 2:
                code, _msg = ct
                raise CasinoError(code, override_msg or _msg)
            else:
                # forma inesperada: pásala tal cual
                raise CasinoError(*ct)
        else:
            # code suelto
            raise CasinoError(ct, override_msg or "Error")
        
    def _update_limits_softcap(self, partner, company, amount):
        """
        Imputa 'amount' a los acumulados de casino.game.bet.limits (diario/semanal/mensual)
        con política soft-cap:
          - Permite si (para todos los períodos con límite > 0) spent <= limit (antes del update).
            Esto deja cruzar el límite en esta jugada.
          - Rechaza si alguno ya estaba spent > limit (antes del update).
        Devuelve dict:
          allowed: bool
          crossed: set de períodos {"daily","weekly","monthly"} que cruzaron/alcan-zaron el límite
          message_map: período->mensaje (desde res.company)
        """
        Bet = request.env['casino.game.bet.limits'].sudo()
        _logger.info(
            'SoftCap: partner=%s company=%s amount=%.6f',
            partner.id, company.id, amount
        )

        # get-or-create, robusto ante concurrencia (unique(partner_id, company_id))
        bl = Bet.search([('partner_id', '=', partner.id), ('company_id', '=', company.id)], limit=1)
        if not bl:
            try:
                with request.env.cr.savepoint():
                    bl = Bet.create({
                        'partner_id': partner.id,
                        'company_id': company.id,
                        'limit_daily': 0.0, 'limit_weekly': 0.0, 'limit_monthly': 0.0,
                        'spent_daily': 0.0, 'spent_weekly': 0.0, 'spent_monthly': 0.0,
                    })
            except IntegrityError:
                request.env.cr.rollback()
                bl = Bet.search([('partner_id', '=', partner.id), ('company_id', '=', company.id)], limit=1)

        # Opcional: ventanas rodantes
        try:
            bl._maybe_roll_windows()
        except Exception:
            pass

        cr = request.env.cr
        _logger.info('SoftCap: UPDATE id=%s amount=%.6f', bl.id, amount)

        # UPDATE atómico: permite cruzar el límite; bloquea si YA estaba excedido (spent > limit)
        cr.execute("""
            UPDATE casino_game_bet_limits bl
               SET spent_daily   = COALESCE(bl.spent_daily,   0) + %(amt)s,
                   spent_weekly  = COALESCE(bl.spent_weekly,  0) + %(amt)s,
                   spent_monthly = COALESCE(bl.spent_monthly, 0) + %(amt)s,
                   last_reset_daily   = COALESCE(bl.last_reset_daily,   NOW()),
                   last_reset_weekly  = COALESCE(bl.last_reset_weekly,  NOW()),
                   last_reset_monthly = COALESCE(bl.last_reset_monthly, NOW())
             WHERE bl.id = %(id)s
               AND (COALESCE(bl.limit_daily,  0) = 0 OR COALESCE(bl.spent_daily,   0) <= COALESCE(bl.limit_daily,  0))
               AND (COALESCE(bl.limit_weekly, 0) = 0 OR COALESCE(bl.spent_weekly,  0) <= COALESCE(bl.limit_weekly, 0))
               AND (COALESCE(bl.limit_monthly,0) = 0 OR COALESCE(bl.spent_monthly, 0) <= COALESCE(bl.limit_monthly,0))
         RETURNING
               COALESCE(bl.spent_daily,   0)             AS new_daily,
               COALESCE(bl.spent_weekly,  0)             AS new_weekly,
               COALESCE(bl.spent_monthly, 0)             AS new_monthly,
               COALESCE(bl.limit_daily,   0)             AS limit_daily,
               COALESCE(bl.limit_weekly,  0)             AS limit_weekly,
               COALESCE(bl.limit_monthly, 0)             AS limit_monthly,
               COALESCE(bl.spent_daily,   0) - %(amt)s   AS prev_daily,
               COALESCE(bl.spent_weekly,  0) - %(amt)s   AS prev_weekly,
               COALESCE(bl.spent_monthly, 0) - %(amt)s   AS prev_monthly
        """, {"id": bl.id, "amt": float(amount or 0.0)})

        if cr.rowcount == 0:
            # Ya estaba excedido antes: identificar período bloqueante (todo coalesceado)
            cr.execute("""
                SELECT
                  COALESCE(spent_daily,   0) AS sd, COALESCE(limit_daily,   0) AS ld,
                  COALESCE(spent_weekly,  0) AS sw, COALESCE(limit_weekly,  0) AS lw,
                  COALESCE(spent_monthly, 0) AS sm, COALESCE(limit_monthly, 0) AS lm
                FROM casino_game_bet_limits
                WHERE id = %s
            """, (bl.id,))
            row = cr.fetchone()
            if not row:
                return {"allowed": True, "crossed": set(), "message_map": {}}

            sd, ld, sw, lw, sm, lm = row

            def exceeded(spent, limit):
                return (limit > 0) and (spent > limit)

            if exceeded(sd, ld):
                msg = bl.company_id.bet_msg_daily or "Has alcanzado tu límite diario."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_DAILY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )
            if exceeded(sw, lw):
                msg = bl.company_id.bet_msg_weekly or "Has alcanzado tu límite semanal."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_WEEKLY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )
            if exceeded(sm, lm):
                msg = bl.company_id.bet_msg_monthly or "Has alcanzado tu límite mensual."
                return self._raise_casino_error(
                    getattr(CasinoErrorCodes, "LIMIT_MONTHLY_EXCEEDED", CasinoErrorCodes.INSUFFICIENT_FUNDS),
                    override_msg=msg
                )

            # sin límites > 0 -> permitir
            return {"allowed": True, "crossed": set(), "message_map": {}}

        # UPDATE aceptado: leer exactamente una vez
        row = cr.fetchone()
        if not row:
            _logger.warning("SoftCap: RETURNING vacío para id=%s (amt=%.6f)", bl.id, amount)
            return {"allowed": True, "crossed": set(), "message_map": {}}

        new_d, new_w, new_m, ld, lw, lm, prev_d, prev_w, prev_m = row
        _logger.info('SoftCap: RETURNING id=%s -> %s', bl.id, row)

        crossed = set()
        if ld > 0 and prev_d <= ld and new_d >= ld:
            crossed.add("daily")
        if lw > 0 and prev_w <= lw and new_w >= lw:
            crossed.add("weekly")
        if lm > 0 and prev_m <= lm and new_m >= lm:
            crossed.add("monthly")

        message_map = {
            "daily":   bl.company_id.bet_msg_daily   or "Has alcanzado tu límite diario.",
            "weekly":  bl.company_id.bet_msg_weekly  or "Has alcanzado tu límite semanal.",
            "monthly": bl.company_id.bet_msg_monthly or "Has alcanzado tu límite mensual.",
        }
        return {"allowed": True, "crossed": crossed, "message_map": message_map}
    
    def _prepare_session_vals(self, game_id, round_id, user_id, token, initial_balance, final_balance, amount, to_win, state, result, transaction_id, internal_transaction_id, json_data, events=None):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product_name = ""
        # if not product_id is None and product_id != 0:
        product = request.env['product.product'].sudo().search([('game_id', '=', game_id)], limit=1)
        #     product_name = product.name

        partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        user_id = user.id

        _logger.info(f"Casino Iframe: Starting game session for product: {product.id} - {product.name}")
        return {
            'game_id': product.id,
            'round_id': round_id,
            'user_id': user_id,
            'token': token,
            'transaction_id': transaction_id,
            'internal_transaction_id': internal_transaction_id,
            'start_datetime': fields.Datetime.now(),
            'end_datetime': fields.Datetime.now() + timedelta(hours=1),
            'result': result,
            'state': state,
            'amount': amount,
            'to_win': to_win,
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'currency_id': request.env.company.currency_id.id,
            'description': f'Inicio de juego: {product_name}',
            'json_data': json_data,
            'events': events or [],
        }

    def _prepare_move_vals(self, token, product, account, debit, credit, op):
        """
        Devuelve los valores para crear un asiento contable balanceado en account.move con dos líneas (account.move.line).
        """
        partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
        cuenta_ingreso = account
        cuenta_contrapartida = request.env['account.account'].sudo().search([
            ('code', '=', '110101')  # Ajusta el código según tu plan contable (ejemplo: caja/banco)
        ], limit=1)
        if not cuenta_contrapartida:
            cuenta_contrapartida = request.env['account.account'].sudo().create({
                'name': 'Contrapartida Casino',
                'code': '110101',
                'account_type': 'asset_receivable',
            })

        return {
            'name': f'Juego: {product}',
            'journal_id': request.env['account.journal'].sudo().search([
                ('type', '=', 'general')], limit=1
            ).id,
            'date': fields.Datetime.today(),
            'ref': f'Casino Game - {product}',
            'line_ids': [
                (0, 0, {
                    'name': f'Ingreso juego: {product}',
                    'account_id': cuenta_ingreso.id,
                    'partner_id': partner.id,
                    'debit': debit,
                    'credit': credit,
                }),
                (0, 0, {
                    'name': 'Ganada' if op == 'win' else 'Perdida' if op == 'lose' else 'Deposito' if op == 'deposit' else 'Place Bet' if op == 'in_progress' else 'Retiro',
                    'account_id': cuenta_contrapartida.id,
                    'partner_id': partner.id,
                    'debit': credit,
                    'credit': debit,
                }),
            ]
        }

    def _get_balance_user(self, token):
        try:
            user = request.env['res.partner'].sudo().search(['|', ('secret_token', '=', token), ('token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            return user.balance_game
            # base_url = request.httprequest.host_url.rstrip('/')
            # url = f'{base_url}/my/movimientos/balance?token={token}'
            # response = requests.get(url, cookies=request.httprequest.cookies)
            # _logger.info('Casino Iframe: Balance response: %s', response.text)
            # balance = response.json().get('balance', 0.0)
            # _logger.info('Casino Iframe: Balance obtenido: %s', balance)
            # return balance
        except Exception as e:
            _logger.error('Casino Iframe: Error en _get_balance_user: %s', str(e))
            return 0.0
        # base_url = request.httprequest.host_url.rstrip('/')
        # url = f'{base_url}/my/movimientos/balance'
        # response = requests.get(url, cookies=request.httprequest.cookies)
        # _logger.info('Casino Iframe: Balance response: %s', response.text)
        # balance = response.json().get('balance', 0.0)
        # return balance
    
    @http.route('/api/v1/start_game', type='json', auth='public', methods=['POST'], csrf=False)
    def start_game(self, product_id, transaction_id, token, **kwargs):
        """
        Registra el inicio de una sesión de juego y movimiento contable
        """
        try:
            # Obtener datos del request
            user = request.env.user
            
            # Buscar el producto
            product_id = None
            if not product_id is None and product_id != 0:
                product_id = int(product_id)
                product = request.env['product.template'].sudo().browse(product_id)
                if not product.exists():
                    return {'error': 'Producto no encontrado'}
            
            # # 1. Registrar en casino.game.session
            # state = 'logged_in'
            # initial_balance = 0.0
            # final_balance = 0.0

            # json_data = {
            #     "token": token,
            #     "balance": initial_balance,
            #     "currency": transaction_id,
            #     "nickname": user.nickname or user.name,
            #     "timestamp": int(time.time() * 1000),
            #     "country": "AR",
            # }
            
            return {
                'success': True,
                'message': 'Sesión iniciada correctamente'
            }
            
        except Exception as e:
            return {
                'error': f'Error al iniciar sesión: {str(e)}'
            }
        
    @http.route('/api/v1/end_game', type='json', auth='public', methods=['POST'], csrf=False)
    def end_game(self, session_id, amount, **kwargs):
        """
        Finaliza una sesión de juego
        """
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

        roundId = data.get('roundId', None)
        if roundId is None:
            roundId = data.get('params', {}).get('roundId')
        # Decodificar si viene como string escapado (ej: "\"9118648\"")
        if isinstance(roundId, str):
            try:
                roundId = json.loads(roundId)
            except (json.JSONDecodeError, ValueError):
                pass  # Mantener el valor original si no se puede decodificar

        gameId = data.get('gameId', None)
        if gameId is None:
            gameId = data.get('params', {}).get('gameId')

        endGame = data.get('endGame', None)
        if endGame is None:
            endGame = data.get('params', {}).get('endGame')

        roundId = data.get('roundId', None)
        if roundId is None:
            roundId = data.get('params', {}).get('roundId')

        transactionId = data.get('transactionId', None)
        if transactionId is None:
            transactionId = data.get('params', {}).get('transactionId')
        
        amount = data.get('amount', 0.0)
        if amount is None:
            amount = data.get('params', {}).get('amount', 0.0)

        to_win = float(data.get('to_win'))
        if to_win is None:
            to_win = float(data['params'].get('toWin', 0.0))
        
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

        if token is None:
            token = data.get('data', {}).get('token')

        internal_transaction_id = token #uuid.uuid4().hex
        session = request.env['casino.game.session'].sudo().search([('secret_token', '=', token)], limit=1)
        result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, to_win=to_win, op='win', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)
        
        # s = request.env['casino.game.session'].sudo().browse(int(session_id))
        
        response = result.get("json_data")
        # {
        #     "balance": result.get("balance", 0.0),
        #     "timestamp": int(time.time() * 1000),
        #     "message": "Fin de juego"
        # }
        return response

    # ===================== API extra (botones) =====================

    @http.route('/api/v1/login', type='http', auth='public', methods=['POST'], csrf=False)
    def api_login(self, **kwargs):
        """
        Login del juego: alias de start_game. Devuelve también balance actual.
        """
        data = request.get_json_data()
        token = data.get('token', None)
        _logger.info('Casino Iframe: token: %s', token)
        _logger.info('*** Casino Iframe json LOGIN: data: %s', json.dumps(data, indent=2, ensure_ascii=False))

        if token is None:
            token = data.get('params', {}).get('token')
        try:
            user = request.env['res.partner'].sudo().search(['|', ('token', '=', token), ('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            _logger.info('Casino Iframe:\napi_login called with kwargs: %s \n----- %s \n----- token: %s \n------ userId: %s \n------', json.dumps(kwargs, indent=2, ensure_ascii=False), data, token, user.id)
            product_id = 0
            transaction_id = 0
            
            result = self.start_game(product_id, transaction_id, token)
            if result.get('error'):
                return result
            session = '' # request.env['casino.game.session'].sudo().browse(result['session_id'])
            
            balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance obtenido: %s', balance)

            if not user.secret_token:
                generated_token = uuid.uuid4().hex
                user.sudo().write({'secret_token': generated_token})
                new_token = generated_token
            else:
                new_token = user.secret_token
            
            response = {
                "token": new_token,
                "balance": int(balance * 100),
                "currency": transaction_id,
                "nickname": user.nickname or user.name,
                "timestamp": int(time.time() * 1000),
                "country": user.country_id.name if user.country_id else "AR",
            }
            return Response(json.dumps(response), content_type='application/json')
            # return response
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            return {'error': f'Error en login: {str(e)}'}

    @http.route('/api/v1/credit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_win(self, **kwargs):
        """Jugada ganada: suma amount al balance."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            _logger.info('*** Casino Iframe json CREDIT: data: %s', json.dumps(data, indent=2, ensure_ascii=False))

            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            gameId = data.get('gameId', None)
            if gameId is None:
                gameId = data.get('params', {}).get('gameId')
            if not gameId:
                raise CasinoError(*CasinoErrorCodes.INVALID_GAME)

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')
            # Decodificar si viene como string escapado
            if isinstance(roundId, str):
                try:
                    roundId = json.loads(roundId)
                except (json.JSONDecodeError, ValueError):
                    pass

            endGame = data.get('endGame', None)
            if endGame is None:
                endGame = data.get('params', {}).get('endGame')

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            transactionId = data.get('transactionId', None)
            if transactionId is None:
                transactionId = data.get('params', {}).get('transactionId')

            amount = data.get('amount', 0.0)
            if amount is None:
                amount = data.get('params', {}).get('amount', 0.0)
            if not isinstance(amount, (int, float)) or amount < 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            internal_transaction_id = uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes
            current_balance = self._get_balance_user(token)

            _logger.info('Casino Iframe: api_win called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            _logger.info('Casino Iframe: Actualizando balance del jugador: %s', json.dumps(kwargs, indent=2, ensure_ascii=False))
            amount = amount / 100
            result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, to_win=0.0, op='win' if amount > 0 else 'lose', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)

            # if result.get('success'):
            #     partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            #     request.env.company.sudo().action_casino_register_cash_movement(
            #         amount=amount,
            #         operation='in',
            #         partner_id=partner.id,
            #         label="Ganancia de juego",
            #         memo=transactionId,
            #     )
                # payment = self.env["casino.transfer.service"].create_internal_transfer_payment(
                #     journal_src=request.env.company.casino_custodia_journal_id,
                #     journal_dst=request.env.casino_operativa_journal_id,
                #     amount=amount,
                #     date=fields.Date.from_string("2025-12-31"),
                #     memo=transactionId,
                #     casino_operation_type="win",
                # )

            response = {
                "balance": int(result.get("balance", 0.0) * 100),
                "transactionId": internal_transaction_id,
                "timestamp": int(time.time() * 1000)
            }
            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            _logger.error('Casino Iframe: Error inesperado en api credit: %s', str(e))
            ce = CasinoError(*CasinoErrorCodes.GENERIC_ERROR)
            return error_response(ce)
        
    @http.route('/api/v1/debit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_lose(self, **kwargs):
        """Jugada perdida: resta amount del balance."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            _logger.info('*** Casino Iframe json DEBIT: data: %s', json.dumps(data, indent=2, ensure_ascii=False))

            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            gameId = data.get('gameId', None)
            if gameId is None:
                gameId = data.get('params', {}).get('gameId')
            if not gameId:
                raise CasinoError(*CasinoErrorCodes.INVALID_GAME)

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')
            # Decodificar si viene como string escapado
            if isinstance(roundId, str):
                try:
                    roundId = json.loads(roundId)
                except (json.JSONDecodeError, ValueError):
                    pass

            endRound = data.get('endRound', None)
            if endRound is None:
                endRound = data.get('params', {}).get('endRound')

            roundId = data.get('roundId', None)
            if roundId is None:
                roundId = data.get('params', {}).get('roundId')

            transactionId = data.get('transactionId', None)
            if transactionId is None:
                transactionId = data.get('params', {}).get('transactionId')

            amount = data.get('amount', 0.0)
            if amount is None:
                amount = data.get('params', {}).get('amount', 0.0)
            if not isinstance(amount, (int, float)) or amount < 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            to_win = data.get('to_win')
            if to_win is None:
                to_win = data.get('params', {}).get('to_win', 0.0)
            if not isinstance(to_win, (int, float)) or to_win < 0:
                to_win = 0.0

            to_win /= 100

            events = data.get('events', [])
            if not events:
                events = data.get('params', {}).get('events', [])
            
            # Asegurar que events sea una lista válida
            if not isinstance(events, list):
                events = None

            # Convertir events a JSON válido
            events = json.dumps(events) if isinstance(events, list) else json.dumps([])

            current_balance = self._get_balance_user(token)
            if amount / 100 > current_balance:
                raise CasinoError(*CasinoErrorCodes.INSUFFICIENT_FUNDS)

            internal_transaction_id = uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes (no aplica para débito, pero puedes agregar otras validaciones aquí)

            _logger.info('Casino Iframe: api_debit called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            amount = amount / 100

            limit_result = self._update_limits_softcap(user, request.env.company, amount)
            #_logger.info('Casino Iframe: Resultado de límites: %s', limit_result)
            op = 'in_progress' if not endRound else 'lose'
            result = self._apply_amount(
                session.id,
                product_id=gameId,
                round_id=roundId,
                amount=amount,
                to_win=to_win,
                op=op,
                token=token,
                transaction_id=transactionId,
                internal_transaction_id=internal_transaction_id,
                events=events
            )

            _logger.info('Casino Iframe: Resultado de la aplicación de monto: %s', result)
            limit_messages = []
            
            _logger.info('Casino Iframe: Mensajes de límite: %s', limit_messages)

            if result.get('success'):
                partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
                # request.env.company.sudo().action_casino_register_cash_movement(
                #     amount=amount,
                #     operation='out_final' if endRound else 'out',
                #     partner_id=partner.id,
                #     label="Ganancia de juego",
                #     memo=transactionId,
                # )

                Session = request.env['casino.game.session'].sudo()
                already_settled = Session.search_count([('transaction_id', '=', transactionId)]) > 1
                if already_settled or op == 'lose':
                    _logger.info("Ya hay sesión para transaction_id=%s; o bien en una jugada pérdida directa (%s), por lo que no se crea pago.", transactionId, op)
                else:
                    payment = request.env["casino.transfer.service"].sudo().create_internal_transfer_payment(
                        journal_src=request.env.company.casino_custodia_journal_id,
                        journal_dst=request.env.company.casino_operativa_journal_id,
                        amount=amount,
                        date=fields.Date.from_string("2025-12-31"),
                        memo=transactionId,
                        casino_operation_type="bet" if not endRound else "lose",
                    )

            response = {
                "balance": int(result.get("balance", 0.0) * 100),
                "transactionId": internal_transaction_id,
                "timestamp": int(time.time() * 1000)
            }

            if limit_messages:
                response["limit_messages"] = limit_messages

            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            _logger.error('Casino Iframe: Error inesperado en api debit: %s', str(e))
            _logger.exception('Casino Iframe: Error inesperado en api debit')
            ce = CasinoError(*CasinoErrorCodes.GENERIC_ERROR)
            return error_response(ce)
    
    @http.route('/api/v1/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, product_id = 0, round_id=None, amount = amount, to_win=0.0, op='refund', token="", transaction_id=None)

    @http.route('/api/v1/balance', type='http', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, **kwargs):
        """Balance: devuelve saldo actual del jugador."""
        try:
            data = request.get_json_data()
            token = data.get('token', None)
            _logger.info('*** Casino Iframe json BALANCE: data: %s', json.dumps(data, indent=2, ensure_ascii=False))

            if token is None:
                    token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            _logger.info('Casino Iframe: api_balance called with token: %s', token)
            user = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            _logger.info('Casino Iframe: api_balance called with token: %s', token)

            current_balance = self._get_balance_user(token)
            response = {
                "balance": int(current_balance * 100),
                "timestamp": int(time.time() * 1000) # now
            }
            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            return {'error': f'Error al obtener balance: {str(e)}'}
        
    @http.route('/api/v1/end', type='json', auth='public', methods=['POST'], csrf=False)
    def api_end(self, session_id, **kwargs):
        """Terminación: alias de end_game."""
        return self.end_game(session_id)


    # ----------------- Helper interno -----------------
    def _apply_amount(self, session_id, product_id, round_id, amount, to_win, op, token, transaction_id, internal_transaction_id, events=None):
        """
        Ajusta el balance de la sesión y deja nota en description.
        op: 'win' | 'lose' | 'refund'
        """
        _logger.info('Casino Iframe: Aplicando monto: %s, operación: %s', amount, op)
        try:
            #s = request.env['casino.game.session'].sudo().browse(int(session_id))
            # if not s.exists():
            #     return {'error': 'Sesión no encontrada'}

            amt = float(amount or 0.0)
            if amt < 0:
                _logger.error('Casino Iframe: Monto negativo inválido: %s', amt)
                return {'error': 'Monto inválido'}

            last_session = request.env['casino.game.session'].sudo().search(
                [('token', '=', token)],
                order='id desc',
                limit=1
            )

            _logger.info("Casino Iframe: Token: %s", token)
            partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
            _logger.info('Casino Iframe: Partner encontrado: %s - %s', partner.id, partner.name)
            user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
            _logger.info('Casino Iframe: Usuario encontrado: %s', user)
            user_id = user.id
            
            current_balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance actual del usuario: %s', current_balance)

            result = ''
            state = None
            credit = 0.0
            debit = 0.0
            
            json_data = {}
            
            if op == 'win':
                _logger.info('Casino Iframe: WIN')

                new_balance = current_balance + amt
                user.balance_game = new_balance
                note = f'Jugada GANADA +{amt}'
                result = 'win'
                state = 'finished'
                credit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": round_id,
                    "transactionId": transaction_id,
                    "amount": amt,
                    "token_live": True,
                }
            elif op == 'lose':
                _logger.info('Casino Iframe: LOSE')
                new_balance = current_balance - amt
                user.balance_game = new_balance
                note = f'Jugada PERDIDA -{amt}'
                result = 'loss'
                state = 'finished'
                debit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": round_id,
                    "transactionId": transaction_id,
                    "amount": amt,
                    "token_live": True,
                }
            elif op == 'in_progress':
                _logger.info('Casino Iframe: Pendiente')
                new_balance = current_balance - amt
                user.balance_game = new_balance
                result = 'in_progress'
                state = 'in_progress'
                debit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": round_id,
                    "transactionId": transaction_id,
                    "amount": amt,
                    "token_live": True,
                }
                # Solo agregar events si es una lista no vacía
                if events and isinstance(events, list) and len(events) > 0:
                    json_data["events"] = events
            elif op == 'refund':
                _logger.info('Casino Iframe: REFUND')
                new_balance = current_balance + amt
                user.balance_game = new_balance
                note = f'Devolución +{amt}'
                result = 'abandoned'
                state = 'finished'
                debit = amt
            elif op == 'balance':
                _logger.info('Casino Iframe: BALANCE')
                new_balance = current_balance
                note = f'Estado de Balance: {new_balance}'
                result = 'balance'
                state = 'finished'
                json_data = {
                    "token": token
                }
            elif op == 'finished':
                _logger.info('Casino Iframe: FINISHED')
                new_balance = current_balance + amt
                note = f'Juego terminado. Balance final: {new_balance}'
                result = 'win'
                state = 'finished'
                credit = amt
                json_data = {
                    "balance": new_balance,
                    "timestamp": int(time.time() * 1000),
                    "message": "Fin de juego"
                }
            else:
                _logger.error('Casino Iframe: Operación inválida: %s', op)
                return {'error': 'Operación inválida'}

            _logger.info('Casino Iframe: Creando session')
            _logger.info('Valores para session_vals: product_id=%s, user_id=%s, token=%s, current=%s, new_balance=%s, amt=%s, state=%s, result=%s, transaction_id=%s, json_data=%s',
                product_id, user_id, token, current_balance, new_balance, amt, state, result, transaction_id, json_data)
            try:
                session_vals = self._prepare_session_vals(product_id, round_id, user_id, token, current_balance, new_balance, amt, to_win, state, result, transaction_id, internal_transaction_id, json_data, events)
            except Exception as e:
                _logger.error('Error en _prepare_session_vals: %s', str(e))
                raise
            _logger.info('Casino Iframe: Session creada %s', session_vals)

            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session.read())
            request.env['bus.bus']._sendone(
                partner, "casino_wallet_update", {"partner_id": partner.id, "balance": partner.balance_game}
            )
            
            account = request.env['account.account'].sudo().search([
                ('code', '=', '400001')
            ], limit=1)
            
            if not account:
                # Crear cuenta si no existe
                account = request.env['account.account'].sudo().create({
                    'name': 'Cuenta Juegos Casino',
                    'code': '400001',
                    'account_type': 'income',
                })

            _logger.info('Casino Iframe: Cuenta contable encontrada o creada: %s', account)
            move_vals = self._prepare_move_vals(token, product_id, account, debit, credit, op)
            try:
                if op in ['win', 'lose', 'balance']:
                    move = request.env['account.move'].sudo().create(move_vals)
                    _logger.info('Asiento contable creado correctamente: %s', move)
            except Exception as e:
                _logger.error('Error al crear el asiento contable: %s', str(e))
                raise
            
            return {'success': True, 'balance': new_balance, 'transaction_id': transaction_id, 'session_id': session.id, 'state': state, 'result': result, 'json_data': json_data}
        except Exception as e:
            _logger.error('Casino Iframe: Error al aplicar monto: %s', str(e))
            return {'error': f'Error al aplicar monto: {str(e)}'}

    @http.route('/api/v1/get_token', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_token(self, user_id=None, **kwargs):
        """Obtención de token."""
        if not user_id:
            return {"error": "user_id requerido"}

        user = request.env['res.users'].sudo().browse(int(user_id))
        if not user.exists():
            return {"error": f"Usuario {user_id} no encontrado"}
        
        _logger.info('Casino Iframe: get_token called with user_id: %s', user_id)
        _logger.info('Tipo de user_id: %s, valor: %r', type(user_id), user_id)
        if user_id is not None:
            user_id = int(user_id)

        user = request.env['res.users'].sudo().browse(user_id)
        
        if user.exists():
            user_data = user.read()[0]
        else:
            _logger.info('Casino Iframe: get_token - Usuario no encontrado para user_id %s', user_id)
        partner = user.partner_id
        _logger.info('Casino Iframe: get_token called with user_id: %s, partner: %s', user_id, partner)
        token = partner.token
        response = {
            "token": token,
        }
        _logger.info('Casino Iframe: get_token called with user_id: %s, token: %s', user_id, token)
        return {"token": token}
        