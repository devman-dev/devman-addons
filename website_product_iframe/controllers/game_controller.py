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