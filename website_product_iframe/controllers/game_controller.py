from odoo import http
from odoo.http import request
import json

class GameController(http.Controller):
    
    @http.route('/casino/start_game', type='json', auth='public', methods=['POST'], csrf=False)
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
            session_vals = {
                'name': f'Sesión - {product.name}',
                'game_id': product_id,
                'user_id': user_id,
                'start_datetime': request.env['ir.fields'].Datetime.now(),
                'state': 'in_progress',
                'initial_balance': 0.0,  # Puedes ajustar según tu lógica
                'currency_id': request.env.company.currency_id.id,
                'description': f'Inicio de juego: {product.name}'
            }
            
            session = request.env['casino.game.session'].sudo().create(session_vals)
            
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
                'date': request.env['ir.fields'].Date.today(),
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
    
    @http.route('/casino/end_game', type='json', auth='public', methods=['POST'], csrf=False)
    def end_game(self, session_id, **kwargs):
        """
        Finaliza una sesión de juego
        """
        try:
            session = request.env['casino.game.session'].sudo().browse(int(session_id))
            if session.exists():
                session.write({
                    'end_datetime': request.env['ir.fields'].Datetime.now(),
                    'state': 'finished'
                })
                
                return {'success': True, 'message': 'Sesión finalizada'}
            else:
                return {'error': 'Sesión no encontrada'}
                
        except Exception as e:
            return {'error': f'Error al finalizar sesión: {str(e)}'}

    # ===================== API extra (botones) =====================

    @http.route('/casino/api/login', type='json', auth='public', methods=['POST'], csrf=False)
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

    @http.route('/casino/api/win', type='json', auth='public', methods=['POST'], csrf=False)
    def api_win(self, session_id, amount, **kwargs):
        """Jugada ganada: suma amount al balance."""
        return self._apply_amount(session_id, amount, op='win')

    @http.route('/casino/api/lose', type='json', auth='public', methods=['POST'], csrf=False)
    def api_lose(self, session_id, amount, **kwargs):
        """Jugada perdida: resta amount del balance."""
        return self._apply_amount(session_id, amount, op='lose')

    @http.route('/casino/api/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def api_refund(self, session_id, amount, **kwargs):
        """Devolución de plata: suma amount al balance (crédito)."""
        return self._apply_amount(session_id, amount, op='refund')

    @http.route('/casino/api/end', type='json', auth='public', methods=['POST'], csrf=False)
    def api_end(self, session_id, **kwargs):
        """Terminación: alias de end_game."""
        return self.end_game(session_id)

    @http.route('/casino/api/balance', type='json', auth='public', methods=['POST'], csrf=False)
    def api_balance(self, session_id, **kwargs):
        """Balance: devuelve saldo actual y estado de la sesión."""
        try:
            s = request.env['casino.game.session'].sudo().browse(int(session_id))
            if not s.exists():
                return {'error': 'Sesión no encontrada'}
            bal = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)
            return {'success': True, 'balance': bal, 'state': s.state}
        except Exception as e:
            return {'error': f'Error al obtener balance: {str(e)}'}

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

            current = s.final_balance if s.final_balance not in (None, False) else (s.initial_balance or 0.0)

            if op == 'win':
                new_balance = current + amt
                note = f'Jugada GANADA +{amt}'
            elif op == 'lose':
                new_balance = current - amt
                note = f'Jugada PERDIDA -{amt}'
            elif op == 'refund':
                new_balance = current + amt
                note = f'Devolución +{amt}'
            else:
                return {'error': 'Operación inválida'}

            # Actualizamos balance y descripción
            timestamp = request.env['ir.fields'].Datetime.now()
            desc = (s.description or '') + f'\n{timestamp}: {note}'
            s.write({
                'final_balance': new_balance,
                'description': desc,
            })

            return {'success': True, 'balance': new_balance}
        except Exception as e:
            return {'error': f'Error al aplicar monto: {str(e)}'}
