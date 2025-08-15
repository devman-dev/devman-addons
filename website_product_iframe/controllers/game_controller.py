from datetime import timedelta
from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)
class GameController(http.Controller):

    def _prepare_session_vals(self, product_id, user_id, initial_balance, final_balance, amount, state, result):
        """
        Devuelve los valores para crear una sesión de juego.
        """
        product = request.env['product.template'].sudo().browse(product_id)
        return {
            'game_id': product_id,
            'user_id': user_id,
            'start_datetime': fields.Datetime.now(),
            'end_datetime': fields.Datetime.now() + timedelta(hours=1),
            'result': result,
            'state': state,
            'amount': amount,
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'currency_id': request.env.company.currency_id.id,
            'description': f'Inicio de juego: {product.name}'
        }

    def _prepare_move_vals(self, product, account, debit, credit):
        """
        Devuelve los valores para crear un asiento contable asociado al juego.
        """
        return {
            'name': f'Juego: {product.name}',
            'journal_id': request.env['account.journal'].sudo().search(
                [('type', '=', 'general')], limit=1
            ).id,
            'date': fields.Datetime.today(),
            'ref': f'Casino Game - {product.name}',
            'line_ids': [
                (0, 0, {
                    'name': f'Inicio juego: {product.name}',
                    'account_id': account.id,
                    'partner_id': request.env.user.partner_id.id,
                    'debit': debit,
                    'credit': credit,
                })
            ]
        }
    
    @http.route('/api/v1/start_game', type='json', auth='public', methods=['POST'], csrf=False)
    def start_game(self, product_id, **kwargs):
        """
        Registra el inicio de una sesión de juego y movimiento contable
        """
        try:
            # Obtener datos del request
            product_id = int(product_id)
            user_id = request.env.user.id
            
            # Buscar el producto
            product = request.env['product.template'].sudo().browse(product_id)
            if not product.exists():
                return {'error': 'Producto no encontrado'}
            
            # 1. Registrar en casino.game.session
            state = 'in_progress'
            initial_balance = 0.0
            final_balance = 0.0
            session_vals = self._prepare_session_vals(product_id, user_id, initial_balance, final_balance, 0, state, result=None)
            
            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Sesión creada en start_game: %s', session)
            # session_vals = {
            #     # 'name': f'Sesión - {product.name}',
            #     'game_id': product_id,
            #     'user_id': user_id,
            #     'start_datetime': fields.Datetime.now(),
            #     'state': 'in_progress',
            #     'initial_balance': 0.0,  # Puedes ajustar según tu lógica
            #     'currency_id': request.env.company.currency_id.id,
            #     'description': f'Inicio de juego: {product.name}'
            # }
            
            # session = request.env['casino.game.session'].sudo().create(session_vals)
            
            # 2. Registrar movimiento contable (account.move.line)
            # Buscar o crear cuenta contable para juegos
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
            
            # Crear asiento contable
            move_vals = {
                'name': f'Juego: {product.name}',
                'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                'date': fields.Datetime.today(),
                'ref': f'Casino Game - {product.name}',
                'line_ids': [
                    (0, 0, {
                        'name': f'Inicio juego: {product.name}',
                        'account_id': account.id,
                        'partner_id': request.env.user.partner_id.id,
                        'debit': 0.0,
                        'credit': 0.0,  # Ajustar según tu lógica de negocio
                    })
                ]
            }
            debit = 0.0
            credit = 0.0

            move_vals = self._prepare_move_vals(product, account, debit, credit)
            move = request.env['account.move'].sudo().create(move_vals)
            
            return {
                'success': True,
                'session_id': session.id,
                'move_id': move.id,
                'iframe_url': product.iframe_url,
                'message': 'Sesión iniciada correctamente'
            }
            
        except Exception as e:
            return {
                'error': f'Error al iniciar sesión: {str(e)}'
            }
    
    @http.route('/api/v1/end_game', type='json', auth='public', methods=['POST'], csrf=False)
    def end_game(self, session_id, **kwargs):
        """
        Finaliza una sesión de juego
        """
        try:
            session = request.env['casino.game.session'].sudo().browse(int(session_id))
            if session.exists():
                session.write({
                    'end_datetime': fields.Datetime.Datetime.now(),
                    'state': 'finished'
                })
                
                return {'success': True, 'message': 'Sesión finalizada'}
            else:
                return {'error': 'Sesión no encontrada'}
                
        except Exception as e:
            return {'error': f'Error al finalizar sesión: {str(e)}'}

    # ===================== API extra (botones) =====================

    @http.route('/api/v1/login', type='json', auth='public', methods=['POST'], csrf=False)
    def api_login(self, product_id, **kwargs):
        """
        Login del juego: alias de start_game. Devuelve también balance actual.
        """
        try:
            resp = self.start_game(product_id)
            if resp.get('error'):
                return resp
            session = request.env['casino.game.session'].sudo().browse(resp['session_id'])
            balance = session.final_balance if session.final_balance not in (None, False) else (session.initial_balance or 0.0)
            resp['balance'] = balance
            
            return resp
        except Exception as e:
            return {'error': f'Error en login: {str(e)}'}

    @http.route('/api/v1/credit', type='json', auth='public', methods=['POST'], csrf=False)
    def api_win(self, session_id, amount, **kwargs):
        """Jugada ganada: suma amount al balance."""
        return self._apply_amount(session_id, amount, op='win')

    @http.route('/api/v1/debit', type='json', auth='public', methods=['POST'], csrf=False)
    def api_lose(self, session_id, amount, **kwargs):
        """Jugada perdida: resta amount del balance."""
        return self._apply_amount(session_id, amount, op='lose')

    @http.route('/api/v1/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, amount, op='refund')

    @http.route('/api/v1/balance', type='json', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, session_id, **kwargs):
        """Balance: devuelve saldo actual y estado de la sesión."""
        try:
            s = request.env['casino.game.session'].sudo().browse(int(session_id))
            if not s.exists():
                return {'error': 'Sesión no encontrada'}
            bal = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)
            return self._apply_amount(session_id, bal, op='finished')
            # return {'success': True, 'balance': bal, 'state': s.state}
        except Exception as e:
            return {'error': f'Error al obtener balance: {str(e)}'}
        
    @http.route('/api/v1/end', type='json', auth='public', methods=['POST'], csrf=False)
    def api_end(self, session_id, **kwargs):
        """Terminación: alias de end_game."""
        return self.end_game(session_id)


    # ----------------- Helper interno -----------------
    def _apply_amount(self, session_id, amount, op):
        """
        Ajusta el balance de la sesión y deja nota en description.
        op: 'win' | 'lose' | 'refund'
        """
        try:
            s = request.env['casino.game.session'].sudo().browse(int(session_id))
            if not s.exists():
                return {'error': 'Sesión no encontrada'}


            try:
                amt = float(amount or 0.0)
            except Exception:
                return {'error': 'Monto inválido'}
            if amt < 0:
                return {'error': 'Monto inválido'}

            last_session = request.env['casino.game.session'].sudo().search(
                [('game_id', '=', s.game_id.id),
                 ('user_id', '=', s.user_id.id)],
                order='id desc',
                limit=1
            )
            
            # current = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)
            current = last_session.final_balance if last_session and last_session.final_balance not in (None, False) else (last_session.initial_balance or 0.0)
            result = ''
            state = s.state
            credit = 0.0
            debit = 0.0
            if op == 'win':
                new_balance = current + amt
                note = f'Jugada GANADA +{amt}'
                result = 'win'
                credit = amt
            elif op == 'lose':
                new_balance = current - amt
                note = f'Jugada PERDIDA -{amt}'
                result = 'loss'
                debit = amt
            elif op == 'refund':
                new_balance = current + amt
                note = f'Devolución +{amt}'
                result = 'abandoned'
                state = 'finished'
                debit = amt
            elif op == 'finished':
                new_balance = current
                note = f'Juego terminado. Balance final: {new_balance}'
                if amount >= 0.0:
                    result = 'win'
                else:
                    result = 'loss'
                state = 'finished'
            else:
                return {'error': 'Operación inválida'}

            session_vals = self._prepare_session_vals(s.game_id.id, s.user_id.id, last_session.final_balance, new_balance, amt, state, result)
            
            session = request.env['casino.game.session'].sudo().create(session_vals)
            _logger.info('Sesión creada en _apply_amount: %s', session)
            _logger.info('Sesión creada en _apply_amount: %s', session.read())
            
            # timestamp = fields.Datetime.now()
            # desc = (s.description or '') + f'\n{timestamp}: {note}'
            # s.write({
            #     'final_balance': new_balance,
            #     'description': desc,
            # })


            # account = request.env['account.account'].sudo().search([
            #     ('code', '=', '400001')  # Ajusta según tu plan contable
            # ], limit=1)
            
            # if not account:
            #     # Crear cuenta si no existe
            #     account = request.env['account.account'].sudo().create({
            #         'name': 'Cuenta Juegos Casino',
            #         'code': '400001',
            #         'account_type': 'income',
            #     })
            # move_vals = self._prepare_move_vals(s.game_id, account, debit, credit)
            # move = request.env['account.move'].sudo().create(move_vals)

            # Actualizamos balance y descripción
            if debit + credit != 0:
                income_account = s.game_id.property_account_income_id.id
                expense_account = s.game_id.property_account_expense_id.id

                move_vals = {
                    'name': f'Juego: {s.game_id.name}',
                    'journal_id': request.env['account.journal'].sudo().search([('type', '=', 'general')], limit=1).id,
                    'date': fields.Datetime.today(),
                    'ref': f'Casino Game - {s.game_id.name}',
                    'line_ids': [
                        (0, 0, {
                            'name': f'Inicio juego: {s.game_id.name}',
                            'account_id': income_account,
                            'partner_id': request.env.user.partner_id.id,
                            'debit': debit,
                            'credit': credit,
                        }),
                        (0, 0, {
                            'name': f'Contrapartida: {s.game_id.name}',
                            'account_id': expense_account,
                            'partner_id': request.env.user.partner_id.id,
                            'debit': credit,
                            'credit': debit,
                        }),
                    ]
                }

                # move = request.env['account.move'].sudo().create(move_vals)

           

            _logger.info('Valor de s: %s', s)
            _logger.info('Campos de s: %s', s.read())
            
            return {'success': True, 'balance': new_balance}
        except Exception as e:
            return {'error': f'Error al aplicar monto: {str(e)}'}
