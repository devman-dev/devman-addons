from datetime import timedelta, datetime
from dataclasses import dataclass, asdict
from typing import Optional, List
import token

import requests
from odoo import http, fields
from odoo.http import request, route, Response
import logging
import time
import uuid
from dataclasses import replace
import json
_logger = logging.getLogger(__name__)

@dataclass
class CasinoTransaction:
    session_id: int
    product_id: int
    end_round: bool
    round_id: Optional[str]
    amount: float
    to_win: float
    op: str  # 'win' | 'lose' | 'in_progress' | 'refund' | 'balance' | 'finished'
    token: str
    transaction_id: Optional[str]
    internal_transaction_id: Optional[str]
    result: Optional[str] = None
    state: Optional[str] = None
    initial_balance: Optional[float] = None
    final_balance: Optional[float] = None
    currency_id: Optional[int] = None
    description: Optional[str] = None
    events: Optional[List] = None
    event_id: Optional[str] = None
    event_date: Optional[str] = None
    market_id: Optional[str] = None
    start: Optional[str] = None
    json_data: Optional[dict] = None

    def __post_init__(self):
        """Validar datos al crear"""
        if self.amount < 0:
            raise ValueError(f"Monto inválido: {self.amount}")
        if self.op not in ['win', 'lose', 'in_progress', 'refund', 'balance', 'finished', 'cancelled']:
            raise ValueError(f"Operación inválida: {self.op}")

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
    
    #def _prepare_session_vals(self, game_id, round_id, user_id, token, initial_balance, final_balance, amount, to_win, state, result, transaction_id, internal_transaction_id, json_data, events=None):
    def _prepare_session_vals(self, transaction: CasinoTransaction):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product_name = ""
        # if not product_id is None and product_id != 0:
        product = request.env['product.product'].sudo().search([('game_id', '=', transaction.product_id)], limit=1)
        #     product_name = product.name

        partner = request.env['res.partner'].sudo().search([('secret_token', '=', transaction.token)], limit=1)
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        user_id = user.id

        _logger.info(f"Casino Iframe: Starting game session for product: {product.id} - {product.name}")
        return {
            'game_id': product.id,
            'end_round': transaction.end_round,
            'round_id': transaction.round_id,
            'user_id': user_id,
            'token': transaction.token,
            'transaction_id': transaction.transaction_id,
            'internal_transaction_id': transaction.internal_transaction_id,
            'start_datetime': fields.Datetime.now(),
            # 'end_datetime': fields.Datetime.now() + timedelta(hours=1),
            'result': transaction.result,
            'state': transaction.state,
            'amount': transaction.amount,
            'to_win': transaction.to_win,
            'initial_balance': transaction.initial_balance,
            'final_balance': transaction.final_balance,
            'currency_id': request.env.company.currency_id.id,
            'description': f'Inicio de juego: {product_name}',
            'json_data': transaction.json_data,
            'events': transaction.events or [],
            'event_id': transaction.event_id,
            'event_date': transaction.event_date,
            'market_id': transaction.market_id,
            'start': transaction.start,
            'json_data': transaction.json_data
        }

    def _prepare_move_vals(self, token, product, account, debit, credit, op, round_id=None, transaction_id=None, event_id=None, event_date=None, market_id=None, start=None):
        """
        Devuelve los valores para crear un asiento contable balanceado en account.move con dos líneas (account.move.line).
        """
        partner = request.env['res.partner'].sudo().search([('secret_token', '=', token)], limit=1)
        cuenta_ingreso = account
        
        # Usar cuenta del diario de Custodia
        custodia_journal = request.env.company.sudo().casino_custodia_journal_id
        if custodia_journal and custodia_journal.default_account_id:
            cuenta_contrapartida = custodia_journal.default_account_id
        else:
            # Fallback a búsqueda por código
            cuenta_contrapartida = request.env['account.account'].sudo().search([('code', '=', '110101')], limit=1)
            if not cuenta_contrapartida:
                cuenta_contrapartida = request.env['account.account'].sudo().create({
                    'name': 'Contrapartida Casino',
                    'code': '110101',
                    'account_type': 'asset_receivable',
                })

        name_parts = []
        if event_id:
            name_parts.append(str(event_id).strip("(),'\""))
        if market_id:
            name_parts.append(str(market_id).strip("(),'\""))
        name_parts.append(product)
        name_parts.append(transaction_id)

        name = " - ".join(name_parts)
        name_line = 'WIN' if op == 'win' else 'LOSE' if op == 'lose' else 'DEPOSIT' if op == 'deposit' else 'PLACE BET' if op == 'in_progress' else 'WITHDRAW'
        name_line += ' - ' + name

        unique_name = name
        # if transaction_id:
        #     unique_name = f'{unique_name} - {transaction_id}'
        # if round_id:
        #     unique_name = f'{unique_name} - {round_id}'

        return {
            'name': unique_name,
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
                    'name': name_line, #'WIN' if op == 'win' else 'LOSE' if op == 'lose' else 'DEPOSIT' if op == 'deposit' else 'PLACE BET' if op == 'in_progress' else 'WITHDRAW',
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
        
        transaction = CasinoTransaction(
            session_id=session.id,
            product_id=gameId,
            round_id=roundId,
            amount=amount,
            to_win=to_win,
            op='win',
            token=token,
            transaction_id=transactionId,
            internal_transaction_id=internal_transaction_id
        )
        result = self._apply_amount(transaction)
        
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

            end_round = data.get('endRound')
            if end_round is None:
                end_round = data.get('params', {}).get('endRound', False)

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

            # _logger.info('Casino Iframe: api_win called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            _logger.info('Casino Iframe: Actualizando balance del jugador: %s', json.dumps(kwargs, indent=2, ensure_ascii=False))
            amount = amount / 100

            op = 'cancelled' if 'CANCELLED' in str(transactionId).upper() else ('win' if amount > 0 else 'lose')
            # result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, to_win=0.0, op=op, token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)
            

            events = data.get('events', [])
            if not events:
                events = data.get('params', {}).get('events', [])
            
            # Asegurar que events sea una lista válida
            if not isinstance(events, list):
                events = None

            # Convertir events a JSON válido
            events = json.dumps(events) if isinstance(events, list) else json.dumps([])

            previous_sessions = request.env['casino.game.session'].sudo().search([
                ('round_id', '=', roundId)
            ], limit=1)
            
            event_id = None
            event_date = None
            market_id = None
            start = None

            if previous_sessions:
                event_id = previous_sessions.event_id
                event_date = previous_sessions.event_date
                market_id = previous_sessions.market_id

            transaction = CasinoTransaction(
                session_id=1, #session.id,
                product_id=gameId,
                end_round=end_round,
                round_id=roundId,
                amount=amount,
                to_win=0.0,
                op=op,
                token=token,
                transaction_id=transactionId,
                internal_transaction_id=internal_transaction_id,
                events=events,
                event_id=event_id,
                event_date=event_date,
                market_id=market_id,
                start=start,
                json_data=data
            )

            result = self._apply_amount(transaction)

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

            end_round = data.get('endRound', False)
            if end_round is None:
                end_round = data.get('params', {}).get('endRound', False)
                
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

            transactionId = data.get('transactionId', None)
            if transactionId is None:
                transactionId = data.get('params', {}).get('transactionId')

            amount = data.get('amount', 0.0)
            if amount is None:
                amount = data.get('params', {}).get('amount', 0.0)
            if not isinstance(amount, (int, float)) or amount < 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            event_id = data.get('event_id', None)
            if event_id is None:
                event_id = data.get('params', {}).get('event_id')
            
            to_win = data.get('to_win')
            if to_win is None:
                to_win = data.get('params', {}).get('to_win', 0.0)
            if not isinstance(to_win, (int, float)) or to_win < 0:
                to_win = 0.0

            to_win /= 100

            event_date = data.get('event_date', None)
            if event_date is None:
                event_date = data.get('params', {}).get('event_date')

            market_id = data.get('market_id', None)
            if market_id is None:
                market_id = data.get('params', {}).get('market_id')

            start = data.get('start', None)
            if start is None:
                start = data.get('params', {}).get('start')

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
            
            transaction = CasinoTransaction(
                session_id=session.id,
                product_id=gameId,
                end_round=end_round,
                round_id=roundId,
                amount=amount,
                to_win=to_win,
                op=op,
                token=token,
                transaction_id=transactionId,
                internal_transaction_id=internal_transaction_id,
                events=json.loads(events) if isinstance(events, str) else events,
                event_id=event_id,
                event_date=event_date,
                market_id=market_id,
                start=start,
                json_data=data
            )
            
            result = self._apply_amount(transaction)

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
    def api_refund(self, session_id, amount, token, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        transaction = CasinoTransaction(
            session_id=session_id,
            product_id=0,
            round_id=None,
            amount=amount,
            to_win=0.0,
            op='refund',
            token=token,
            transaction_id=None,
            internal_transaction_id=uuid.uuid4().hex
        )
        return self._apply_amount(transaction)

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
        return self.end_game(session_id, 0.0)


    # ----------------- Helper interno -----------------
    #def _apply_amount(self, session_id, product_id, round_id, amount, to_win, op, token, transaction_id, internal_transaction_id, events=None):
    def _apply_amount(self, transaction: CasinoTransaction):
        """
        Ajusta el balance de la sesión y deja nota en description.
        op: 'win' | 'lose' | 'refund'
        
        Args:
            transaction: CasinoTransaction con todos los parámetros de la transacción
        """
        # Extraer todos los campos del dataclass
        amt = float(transaction.amount or 0.0)
        op = transaction.op
        token = transaction.token
        product_id = transaction.product_id
        end_round = transaction.end_round
        round_id = transaction.round_id
        transaction_id = transaction.transaction_id
        internal_transaction_id = transaction.internal_transaction_id
        to_win = transaction.to_win
        events = transaction.events
        session_id = transaction.session_id
        event_id = transaction.event_id
        event_date = transaction.event_date
        market_id = transaction.market_id
        start = transaction.start
        full_data = transaction.json_data
        
        # Obtener producto para el nombre
        product = request.env['product.product'].sudo().search([('game_id', '=', product_id)], limit=1)
        product_name = product.name if product else "Desconocido"
        product_game_id = product.game_id if product else product_id
        
        _logger.info('Casino Iframe: Aplicando monto: %s, operación: %s', amt, op)
        try:
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
            
            if op == 'win' or op == 'cancelled':
                _logger.info('Casino Iframe: WIN')

                new_balance = current_balance + amt
                user.balance_game = new_balance
                result = 'win' if op == 'win' else 'cancelled'
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
                credit = 0.0
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
                result = 'abandoned'
                state = 'finished'
                debit = amt
            elif op == 'balance':
                _logger.info('Casino Iframe: BALANCE')
                new_balance = current_balance
                result = 'balance'
                state = 'finished'
                json_data = {
                    "token": token
                }
            elif op == 'finished':
                _logger.info('Casino Iframe: FINISHED')
                new_balance = current_balance + amt
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
                #session_vals = self._prepare_session_vals(product_id, round_id, user_id, token, current_balance, new_balance, amt, to_win, state, result, transaction_id, internal_transaction_id, full_data, events)
                # transaction.new_balance = new_balance
                # transaction.current_balance = current_balance
                # transaction.partner_id = partner.id
                # transaction.user_id = user_id
                new_transaction = replace(transaction, result=result, state=state)
                session_vals = self._prepare_session_vals(new_transaction)
            except Exception as e:
                _logger.error('Error en _prepare_session_vals: %s', str(e))
                raise
            _logger.info('Casino Iframe: Session creada %s', session_vals)

            session = request.env['casino.game.session'].sudo().create(session_vals)
            
            # Si existe una sesión previa con mismo roundId y result='in_progress', finalizarla
            if round_id:
                previous_sessions = request.env['casino.game.session'].sudo().search([
                    ('round_id', '=', round_id),
                    ('result', '=', 'in_progress'),
                    ('id', '!=', session.id)
                ])
                if previous_sessions:
                    previous_sessions.write({'state': 'finished'})
                    _logger.info('Casino Iframe: Sesiones previas finalizadas para roundId %s: %s', round_id, previous_sessions.ids)
            
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session.read())
            request.env['bus.bus']._sendone(
                partner, "casino_wallet_update", {"partner_id": partner.id, "balance": partner.balance_game}
            )
            
            # Usar cuenta del diario operativa para ingresos de juegos
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

            _logger.info('Casino Iframe: Cuenta contable encontrada o creada: %s', account)
            move_vals = self._prepare_move_vals(token, product_name, account, debit, credit, op, round_id=round_id, transaction_id=transaction_id, event_id=event_id, market_id=market_id)
            try:
                # Para in_progress, solo crear movimiento de custodia; para win/lose crear movimiento general
                if op in ['win', 'lose'] and amt >= 0:
                    move = request.env['account.move'].sudo().create(move_vals)
                    _logger.info('Asiento contable creado correctamente: %s', move)
                    
                    # Postear el move para que se registren las líneas en la contabilidad
                    if move.state == 'draft':
                        move.action_post()
                        _logger.info('Asiento contable posteado: %s', move.id)
                    
                # Si es in_progress, crear movimiento desde el diario de Custodia
                if op == 'in_progress':
                    custodia_journal = request.env.company.sudo().casino_custodia_journal_id
                    if custodia_journal:
                        _logger.info('Creando movimiento de salida desde Custodia para in_progress')
                        
                        # Obtener la cuenta default del journal con sudo
                        default_account = custodia_journal.sudo().default_account_id
                        if not default_account:
                            default_account = request.env['account.account'].sudo().search([('code', '=', '110101')], limit=1)
                        
                        # Construir nombre limpio sin tuplas
                        # Formatear fecha de forma que no sea interpretada como fecha real
                        meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 
                                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
                        
                        # Convertir day_event a fecha real si existe, sino usar hoy
                        if transaction.event_date:
                            try:
                                # Si viene como string ISO (ej: "2026-01-15"), parsearlo
                                from datetime import datetime
                                if isinstance(transaction.event_date, str):
                                    event_date_obj = datetime.fromisoformat(transaction.event_date).date()
                                else:
                                    event_date_obj = transaction.event_date
                                fecha_formateada = f"En {event_date_obj.day} de {meses[event_date_obj.month - 1]}"
                            except (ValueError, AttributeError):
                                # Si falla el parseo, usar hoy
                                today = fields.Date.today()
                                fecha_formateada = f"En {today.day} de {meses[today.month - 1]}"
                        else:
                            today = fields.Date.today()
                            fecha_formateada = f"En {today.day} de {meses[today.month - 1]}"
                        
                        if transaction.start:
                            try:
                                # Si viene como string ISO (ej: "2026-01-15"), parsearlo
                                from datetime import datetime
                                if isinstance(transaction.start, str):
                                    event_date_obj = datetime.fromisoformat(transaction.start).date()
                                else:
                                    event_date_obj = transaction.start
                                fecha_start_formateada = f"En {event_date_obj.day} de {meses[event_date_obj.month - 1]}"
                            except (ValueError, AttributeError):
                                # Si falla el parseo, usar hoy
                                today = fields.Date.today()
                                fecha_start_formateada = f"En {today.day} de {meses[today.month - 1]}"
                        else:
                            today = fields.Date.today()
                            fecha_start_formateada = f"En {today.day} de {meses[today.month - 1]}"

                        # Construir name_parts dinámicamente: solo agregar si existe
                        name_parts = []
                        if event_id:
                            name_parts.append(str(event_id).strip("(),'\""))
                        if market_id:
                            name_parts.append(str(market_id).strip("(),'\""))
                        name_parts.append(product_name)
                        name_parts.append(transaction_id)

                        name = " - ".join(name_parts)
                        
                        custodia_move_vals = {
                            'name': name,
                            'journal_id': custodia_journal.id,
                            'date': fields.Date.today(),
                            'ref': f'Casino Game In Progress - {product_game_id}',
                            'line_ids': [
                                (0, 0, {
                                    'name': 'BET ' + name, #f'BET',
                                    'account_id': default_account.id,
                                    'partner_id': partner.id,
                                    'debit': 0.0,
                                    'credit': amt,
                                }),
                                (0, 0, {
                                    'name': f'{transaction_id} - {product_game_id} - Contrapartida - Juego en progreso',
                                    'account_id': account.id,
                                    'partner_id': partner.id,
                                    'debit': amt,
                                    'credit': 0.0,
                                }),
                            ]
                        }
                        custodia_move = request.env['account.move'].sudo().create(custodia_move_vals)
                        _logger.info('Movimiento de Custodia creado: %s', custodia_move.id)
                        
                        if custodia_move.state == 'draft':
                            custodia_move.action_post()
                            _logger.info('Movimiento de Custodia posteado: %s', custodia_move.id)
                    else:
                        _logger.warning('No se encontró diario de Custodia en la compañía')
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
        