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
    def _prepare_session_vals(self, game_id, round_id, user_id, token, initial_balance, final_balance, amount, state, result, transaction_id, internal_transaction_id, json_data):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product_name = ""
        # if not product_id is None and product_id != 0:
        product = request.env['product.product'].sudo().search([('game_id', '=', game_id)], limit=1)
        #     product_name = product.name

        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
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
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'currency_id': request.env.company.currency_id.id,
            'description': f'Inicio de juego: {product_name}',
            'json_data': json_data
        }

    def _prepare_move_vals(self, token, product, account, debit, credit, op):
        """
        Devuelve los valores para crear un asiento contable balanceado en account.move con dos líneas (account.move.line).
        """
        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
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
                    'name': 'Ganada' if op == 'win' else 'Perdida' if op == 'lose' else 'Deposito' if op == 'deposit' else 'Retiro',
                    'account_id': cuenta_contrapartida.id,
                    'partner_id': partner.id,
                    'debit': credit,
                    'credit': debit,
                }),
            ]
        }

    def _get_balance_user(self, token):
        try:
            user = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
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

        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

        if token is None:
            token = data.get('data', {}).get('token')

        internal_transaction_id = token #uuid.uuid4().hex
        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
        result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, op='win', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)
        
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
        userId = request.env.user.id
        # data = request.params
        # token = data.get('token')
        if token is None:
            token = data.get('params', {}).get('token')
        try:
            # user = request.env['res.users'].sudo().browse(userId)
            user = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
            if not user:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)
            
            _logger.info('Casino Iframe:\napi_login called with kwargs: %s \n----- %s \n----- token: %s \n------ userId: %s \n------', json.dumps(kwargs, indent=2, ensure_ascii=False), data, token, user.id)
            product_id = 0
            transaction_id = 0
            internal_transaction_id = token #uuid.uuid4().hex

            result = self.start_game(product_id, transaction_id, token)
            if result.get('error'):
                return result
            session = '' # request.env['casino.game.session'].sudo().browse(result['session_id'])
            
            # base_url = request.httprequest.host_url.rstrip('/')
            # url = f'{base_url}/my/movimientos/balance'
            # response = requests.get(url, cookies=request.httprequest.cookies)
            # _logger.info('Casino Iframe: Balance response: %s', response.text)
            # balance = response.json().get('balance', 0.0)
            balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance obtenido: %s', balance)
            # balance = balance_data.get('balance', 0.00)
            # _logger.info('api_login called balance with session_id: %s, balance: %s', session.id if session else 'N/A', balance)
            response = {
                "token": internal_transaction_id,
                "balance": int(balance * 100),
                "currency": transaction_id,
                "nickname": user.nickname or user.name,
                "timestamp": int(time.time() * 1000),
                "country": user.country_id.name if user.country_id else "AR",

                # 'success': True,
                # 'session_id': result['session_id'],
                # 'move_id': result['move_id'],
                # 'iframe_url': result['iframe_url'],
                # 'message': result['message']
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
            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
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
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            internal_transaction_id = token #uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes
            current_balance = self._get_balance_user(token)
            if current_balance is not None and amount / 100 > current_balance:
                raise CasinoError(*CasinoErrorCodes.INSUFFICIENT_FUNDS)

            _logger.info('Casino Iframe: api_win called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            _logger.info('Casino Iframe: Actualizando balance del jugador: %s', json.dumps(kwargs, indent=2, ensure_ascii=False))
            amount = amount / 100
            result = self._apply_amount(session.id, product_id = gameId, round_id = roundId, amount=amount, op='win', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)
            # s = request.env['casino.game.session'].sudo().browse(int(session_id))
            # now = datetime.now().strftime('%H:%M:%S')

            # Mover la llamada a requests.get después de _apply_amount
            # base_url = request.httprequest.host_url.rstrip('/')
            # url = f'{base_url}/my/movimientos/balance'
            # balance_response = requests.get(url, cookies=request.httprequest.cookies)
            # _logger.info('Casino Iframe: api_win Balance response: %s', balance_response.text)
            # balance = balance_response.json().get('balance', 0.0)

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
            if token is None:
                token = data.get('params', {}).get('token')
            if not token:
                raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            user = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
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
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise CasinoError(*CasinoErrorCodes.INVALID_AMOUNT)

            current_balance = self._get_balance_user(token)
            if amount / 100 > current_balance:
                raise CasinoError(*CasinoErrorCodes.INSUFFICIENT_FUNDS)

            internal_transaction_id = token #uuid.uuid4().hex

            session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
            # if not session:
            #     raise CasinoError(*CasinoErrorCodes.INVALID_TOKEN)

            # Validar fondos insuficientes (no aplica para débito, pero puedes agregar otras validaciones aquí)

            _logger.info('Casino Iframe: api_lose called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
            amount = amount / 100
            result = self._apply_amount(session.id, product_id=gameId, round_id=roundId, amount=amount, op='lose', token=token, transaction_id=transactionId, internal_transaction_id=internal_transaction_id)

            response = {
                "balance": int(result.get("balance", 0.0) * 100),
                "transactionId": internal_transaction_id,
                "timestamp": int(time.time() * 1000)
            }
            return Response(json.dumps(response), content_type='application/json')
        except CasinoError as ce:
            return error_response(ce)
        except Exception as e:
            _logger.error('Casino Iframe: Error inesperado en api debit: %s', str(e))
            ce = CasinoError(*CasinoErrorCodes.GENERIC_ERROR)
            return error_response(ce)
    
    @http.route('/api/v1/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, product_id = 0, round_id=None, amount = amount, op='refund', token="", transaction_id=None)

    @http.route('/api/v1/balance', type='http', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, **kwargs):
        """Balance: devuelve saldo actual del jugador."""
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')
            
        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
        _logger.info('Casino Iframe: api_balance called with token: %s', token)

        try:
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
    def _apply_amount(self, session_id, product_id, round_id, amount, op, token, transaction_id, internal_transaction_id):
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
            partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
            _logger.info('Casino Iframe: Partner encontrado: %s', partner)
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
                state = 'in_progress'
                credit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": "roundId",
                    "transactionId": transaction_id,
                    "amount": amt,
                    "TokenLive": True,
                }
            elif op == 'lose':
                _logger.info('Casino Iframe: LOSE')
                new_balance = current_balance - amt
                user.balance_game = new_balance
                note = f'Jugada PERDIDA -{amt}'
                result = 'loss'
                state = 'in_progress'
                debit = amt
                json_data = {
                    "token": token,
                    "gameId": product_id,
                    "endRound": False,
                    "roundId": "roundId",
                    "transactionId": transaction_id,
                    "amount": amt,
                    "TokenLive": True,
                }
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
                state = 'in_progress'
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
                session_vals = self._prepare_session_vals(product_id, round_id, user_id, token, current_balance, new_balance, amt, state, result, transaction_id, internal_transaction_id, json_data)
            except Exception as e:
                _logger.error('Error en _prepare_session_vals: %s', str(e))
                raise
            _logger.info('Casino Iframe: Session creada %s', session_vals)

            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session.read())
            
            account = request.env['account.account'].sudo().search([
                ('code', '=', '400001')  # Ajusta según tu plan contable
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
        