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
class GameController(http.Controller):

    def _prepare_session_vals(self, product_id, user_id, token, initial_balance, final_balance, amount, state, result, transaction_id, json_data):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product_name = ""
        # if not product_id is None and product_id != 0:
        #     product = request.env['product.template'].sudo().browse(product_id)
        #     product_name = product.name

        partner = request.env['res.partner'].sudo().search([('token', '=', token)], limit=1)
        user = request.env['res.users'].sudo().search([('partner_id', '=', partner.id)], limit=1)
        user_id = user.id

        _logger.info(f"Casino Iframe: Starting game session for product: {product_id} - {product_name}")
        return {
            'game_id': product_id,
            'user_id': user_id,
            'token': token,
            'transaction_id': transaction_id,
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
            base_url = request.httprequest.host_url.rstrip('/')
            url = f'{base_url}/my/movimientos/balance?token={token}'
            response = requests.get(url, cookies=request.httprequest.cookies)
            _logger.info('Casino Iframe: Balance response: %s', response.text)
            balance = response.json().get('balance', 0.0)
            _logger.info('Casino Iframe: Balance obtenido: %s', balance)
            return balance
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
            
            # 1. Registrar en casino.game.session
            state = 'logged_in'
            initial_balance = 0.0
            final_balance = 0.0

            json_data = {
                "token": token,
                "balance": initial_balance,
                "currency": transaction_id,
                "nickname": user.name,
                "timestamp": int(time.time() * 1000),
                "country": "AR",
            }
            
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
        result = self._apply_amount(session_id, amount, op='finished', token=token, transaction_id=None)
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
        user = request.env['res.users'].sudo().browse(userId)

        # data = request.params
        # token = data.get('token')
        if token is None:
            token = data.get('params', {}).get('token')
        _logger.info('Casino Iframe:\napi_login called with kwargs: %s \n----- %s \n----- token: %s \n------ userId: %s \n------', json.dumps(kwargs, indent=2, ensure_ascii=False), data, token, userId)
        try:
            # token = uuid.uuid4().hex  # Genera un token único
            product_id = 0
            transaction_id = 0
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
                "token": token,
                "balance": int(balance * 100),
                "currency": transaction_id,
                "nickname": user.name,
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
        except Exception as e:
            return {'error': f'Error en login: {str(e)}'}

    @http.route('/api/v1/credit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_win(self, **kwargs):
        """Jugada ganada: suma amount al balance."""
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')
        
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

        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)

        _logger.info('Casino Iframe: api_win called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
        _logger.info('Casino Iframe: Actualizando balance del jugador: %s', json.dumps(kwargs, indent=2, ensure_ascii=False))
        amount = amount / 100
        result = self._apply_amount(session.id, product_id = gameId, amount=amount, op='win', token=token, transaction_id=transactionId)
        # s = request.env['casino.game.session'].sudo().browse(int(session_id))
        # now = datetime.now().strftime('%H:%M:%S')

        # Mover la llamada a requests.get después de _apply_amount
        base_url = request.httprequest.host_url.rstrip('/')
        url = f'{base_url}/my/movimientos/balance'
        balance_response = requests.get(url, cookies=request.httprequest.cookies)
        _logger.info('Casino Iframe: api_win Balance response: %s', balance_response.text)
        balance = balance_response.json().get('balance', 0.0)

        response = {
            "balance": int(result.get("balance", 0.0) * 100),
            "transactionId": result.get("transaction_id", None),
            "timestamp": int(time.time() * 1000) # now
        }
        return Response(json.dumps(response), content_type='application/json')
        
    @http.route('/api/v1/debit', type='http', auth='public', methods=['POST'], csrf=False)
    def api_lose(self, **kwargs):
        """Jugada perdida: resta amount del balance."""
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')

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

        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
        _logger.info('Casino Iframe: api_lose called with session_id: %s, amount: %s, transactionId: %s', session.id, amount, transactionId)
        amount = amount / 100
        result = self._apply_amount(session.id, product_id=gameId, amount=amount, op='lose', token=token, transaction_id=transactionId)
        # s = request.env['casino.game.session'].sudo().browse(int(session_id))
        
        # # response = result.get("json_data")
        # base_url = request.httprequest.host_url.rstrip('/')
        # url = f'{base_url}/my/movimientos/balance'
        # response = requests.get(url, cookies=request.httprequest.cookies)
        # _logger.info('Casino Iframe: api_lose Balance response: %s', response.text)
        # balance = response.json().get('balance', 0.0)

        response = {
            "balance": int(result.get("balance", 0.0) * 100),
            "transactionId": result.get("transaction_id"),
            "timestamp": int(time.time() * 1000) # now
        }
        return Response(json.dumps(response), content_type='application/json')
        return response
    
    @http.route('/api/v1/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, product_id = 0, amount = amount, op='refund', token="", transaction_id=None)

    @http.route('/api/v1/balance', type='http', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, **kwargs):
        """Balance: devuelve saldo actual y estado de la sesión."""
        data = request.get_json_data()
        token = data.get('token', None)
        if token is None:
            token = data.get('params', {}).get('token')
            
        session = request.env['casino.game.session'].sudo().search([('token', '=', token)], limit=1)
        _logger.info('Casino Iframe: api_balance called with token: %s', token)

        try:
            # s = request.env['casino.game.session'].sudo().browse(int(session.id))
            # if not s.exists():
            #     return {'error': 'Sesión no encontrada'}
            # bal = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)
            # result = self._apply_amount(session.id, product_id = 0, amount = 0.0, op='balance', token=token, transaction_id=None)
            # _logger.info('Casino Iframe: api_balance called with session_id: %s, amount: %s, result: %s', session.id, 0.0, result)
            # response = result.get("json_data")
            current_balance = self._get_balance_user(token)
            
            response = {
                "balance": int(current_balance * 100),
                "timestamp": int(time.time() * 1000) # now
            }
            return Response(json.dumps(response), content_type='application/json')
        except Exception as e:
            return {'error': f'Error al obtener balance: {str(e)}'}
        
    @http.route('/api/v1/end', type='json', auth='public', methods=['POST'], csrf=False)
    def api_end(self, session_id, **kwargs):
        """Terminación: alias de end_game."""
        return self.end_game(session_id)


    # ----------------- Helper interno -----------------
    def _apply_amount(self, session_id, product_id, amount, op, token, transaction_id):
        """
        Ajusta el balance de la sesión y deja nota en description.
        op: 'win' | 'lose' | 'refund'
        """
        _logger.info('Casino Iframe: Aplicando monto: %s, operación: %s', amount, op)
        try:
            #s = request.env['casino.game.session'].sudo().browse(int(session_id))
            # if not s.exists():
            #     return {'error': 'Sesión no encontrada'}

            try:
                amt = float(amount or 0.0)
            except Exception:
                _logger.error('Casino Iframe: Error al convertir amount a float: %s', amount)
                return {'error': 'Monto inválido'}
            if amt < 0:
                _logger.error('Casino Iframe: Monto negativo inválido: %s', amt)
                return {'error': 'Monto inválido'}

            # last_session = request.env['casino.game.session'].sudo().search(
            #     [('game_id', '=', s.game_id.id),
            #      ('user_id', '=', s.user_id.id)],
            #     order='id desc',
            #     limit=1
            # )
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
            # current = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)
            # current = last_session.final_balance if last_session and last_session.final_balance not in (None, False) else (last_session.initial_balance or 0.0)
            current_balance = self._get_balance_user(token)
            _logger.info('Casino Iframe: Balance actual del usuario: %s', current_balance)

            result = ''
            state = None
            credit = 0.0
            debit = 0.0
            # transaction_id = s.transaction_id
            json_data = {}
            # token = s.token or uuid.uuid4().hex  # Genera un token único si no existe
            if op == 'win':
                _logger.info('Casino Iframe: WIN')
                new_balance = current_balance + amt
                note = f'Jugada GANADA +{amt}'
                result = 'win'
                state = 'in_progress'
                credit = amt
                # json_data = {
                #     "balance": new_balance,
                #     "transactionId": transaction_id,
                #     "timestamp": int(time.time() * 1000) # now
                # }
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
                note = f'Jugada PERDIDA -{amt}'
                result = 'loss'
                state = 'in_progress'
                debit = amt
                # json_data = {
                #     "balance": new_balance,
                #     "transactionId": transaction_id,
                #     "timestamp": int(time.time() * 1000) # now
                # }
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
                # json_data = {
                #     "balance": new_balance,
                #     "timestamp": int(time.time() * 1000) # now
                # }
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
                session_vals = self._prepare_session_vals(product_id, user_id, token, current_balance, new_balance, amt, state, result, transaction_id, json_data)
            except Exception as e:
                _logger.error('Error en _prepare_session_vals: %s', str(e))
                raise
            _logger.info('Casino Iframe: Session creada %s', session_vals)

            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session)
            _logger.info('Casino Iframe: Sesión creada en _apply_amount: %s', session.read())
            
            # timestamp = fields.Datetime.now()
            # desc = (s.description or '') + f'\n{timestamp}: {note}'
            # s.write({
            #     'final_balance': new_balance,
            #     'description': desc,
            # })

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

            # Actualizamos balance y descripción
            # if debit + credit != 0:
            #     income_account = s.game_id.property_account_income_id.id
            #     expense_account = s.game_id.property_account_expense_id.id

            #     move_vals = {
            #         'name': f'Juego: {product_id}',
            #         'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
            #         'date': fields.Datetime.today(),
            #         'ref': f'Casino Game - {s.game_id.name}',
            #         'line_ids': [
            #             (0, 0, {
            #                 'name': f'Inicio juego: {s.game_id.name}',
            #                 'account_id': income_account,
            #                 'partner_id': request.env.user.partner_id.id,
            #                 'debit': debit,
            #                 'credit': credit,
            #             }),
            #             (0, 0, {
            #                 'name': f'Contrapartida: {s.game_id.name}',
            #                 'account_id': expense_account,
            #                 'partner_id': request.env.user.partner_id.id,
            #                 'debit': credit,
            #                 'credit': debit,
            #             }),
            #         ]
            #     }

            #     # move = request.env['account.move'].sudo().create(move_vals)

            # _logger.info('Casino Iframe: Valor de s: %s', s)
            # _logger.info('Casino Iframe: Campos de s: %s', s.read())
            
            return {'success': True, 'balance': new_balance, 'transaction_id': transaction_id, 'session_id': session.id, 'state': state, 'result': result, 'json_data': json_data}
        except Exception as e:
            _logger.error('Casino Iframe: Error al aplicar monto: %s', str(e))
            return {'error': f'Error al aplicar monto: {str(e)}'}

    @http.route('/api/v1/get_token', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def get_token(self, user_id=None, **kwargs):
        """Obtención de token."""
        # data = request.get_json_data()
        # user_id = data.get('user_id', None)
        # if user_id is None:
        #     user_id = data.get('params', {}).get('user_id')

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
        
        # Log completo de los datos del usuario
        if user.exists():
            user_data = user.read()[0]
            # _logger.info('Casino Iframe: get_token - Datos completos de user_id %s: %s', user_id, json.dumps(user_data, indent=2, ensure_ascii=False))
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
        return Response(json.dumps(response), content_type='application/json')
        