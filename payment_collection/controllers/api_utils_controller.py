# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CollectionUtilsAPI(http.Controller):
    """API para operaciones, categorías y otros utilitarios"""
    
    def _validate_auth(self):
        """Validar autenticación del usuario"""
        if not request.env.user or request.env.user._is_public():
            return self._error_response(401, "UNAUTHORIZED", "Autenticación requerida")
        return None
    
    def _success_response(self, data, message="Success"):
        """Respuesta exitosa estándar"""
        return {
            "success": True,
            "data": data,
            "message": message
        }
    
    def _error_response(self, status_code, error_code, message, details=None):
        """Respuesta de error estándar"""
        error_data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            }
        }
        if details:
            error_data["error"]["details"] = details
        
        return error_data
    
    # ==================== ENDPOINTS DE OPERACIONES ====================
    
    @http.route('/api/collection/operations', type='json', auth='user', methods=['GET'], csrf=False)
    def get_operations(self, **kwargs):
        """Obtener lista de operaciones"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Buscar operaciones
            domain = [('collection_type', '=', 'operation')]
            
            if kwargs.get('active_only', True):
                domain.append(('active', '=', True))
            
            operations = request.env['product.template'].sudo().search(domain)
            
            # Serializar datos
            operation_data = [
                {
                    "id": op.id,
                    "name": op.name,
                    "collection_type": getattr(op, 'collection_type', 'operation'),
                    "active": op.active
                }
                for op in operations
            ]
            
            return self._success_response(operation_data)
            
        except Exception as e:
            _logger.error("Error getting operations: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/operations', type='json', auth='user', methods=['POST'], csrf=False)
    def create_operation(self, **kwargs):
        """Crear una nueva operación"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar datos requeridos
            if 'name' not in kwargs:
                return self._error_response(400, "MISSING_FIELD", "Campo requerido: name")
            
            # Preparar datos de la operación
            operation_data = {
                'name': kwargs['name'],
                'collection_type': 'operation',
                'type': 'service',
                'active': kwargs.get('active', True)
            }
            
            # Crear la operación
            operation = request.env['product.template'].sudo().create(operation_data)
            
            return self._success_response({
                "id": operation.id,
                "name": operation.name
            }, "Operación creada exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error creating operation: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    # ==================== ENDPOINTS DE CATEGORÍAS ====================
    
    @http.route('/api/collection/categories', type='json', auth='user', methods=['GET'], csrf=False)
    def get_categories(self, **kwargs):
        """Obtener lista de categorías"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Buscar categorías
            categories = request.env['collection.category'].sudo().search([])
            
            # Serializar datos
            category_data = [
                {
                    "id": cat.id,
                    "name": cat.name
                }
                for cat in categories
            ]
            
            return self._success_response(category_data)
            
        except Exception as e:
            _logger.error("Error getting categories: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/categories', type='json', auth='user', methods=['POST'], csrf=False)
    def create_category(self, **kwargs):
        """Crear una nueva categoría"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar datos requeridos
            if 'name' not in kwargs:
                return self._error_response(400, "MISSING_FIELD", "Campo requerido: name")
            
            # Crear la categoría
            category = request.env['collection.category'].sudo().create({
                'name': kwargs['name']
            })
            
            return self._success_response({
                "id": category.id,
                "name": category.name
            }, "Categoría creada exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error creating category: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/categories/<int:category_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_category(self, category_id, **kwargs):
        """Actualizar categoría"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            category = request.env['collection.category'].sudo().browse(category_id)
            if not category.exists():
                return self._error_response(404, "CATEGORY_NOT_FOUND", "Categoría no encontrada")
            
            if 'name' in kwargs:
                category.name = kwargs['name']
            
            return self._success_response({
                "id": category.id,
                "name": category.name
            }, "Categoría actualizada exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error updating category %s: %s", category_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/categories/<int:category_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_category(self, category_id):
        """Eliminar categoría"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            category = request.env['collection.category'].sudo().browse(category_id)
            if not category.exists():
                return self._error_response(404, "CATEGORY_NOT_FOUND", "Categoría no encontrada")
            
            category.unlink()
            
            return self._success_response({}, "Categoría eliminada exitosamente")
            
        except Exception as e:
            _logger.error("Error deleting category %s: %s", category_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    # ==================== ENDPOINTS DE MONEDAS ====================
    
    @http.route('/api/collection/currencies', type='json', auth='user', methods=['GET'], csrf=False)
    def get_currencies(self, **kwargs):
        """Obtener lista de monedas"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Buscar monedas activas
            currencies = request.env['res.currency'].sudo().search([('active', '=', True)])
            
            # Serializar datos
            currency_data = [
                {
                    "id": curr.id,
                    "name": curr.name,
                    "symbol": curr.symbol,
                    "full_name": curr.full_name or curr.name,
                    "active": curr.active
                }
                for curr in currencies
            ]
            
            return self._success_response(currency_data)
            
        except Exception as e:
            _logger.error("Error getting currencies: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    # ==================== ENDPOINTS DE BANCOS ====================
    
    @http.route('/api/collection/banks', type='json', auth='user', methods=['GET'], csrf=False)
    def get_banks(self, **kwargs):
        """Obtener lista de bancos"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Buscar bancos activos
            banks = request.env['res.bank'].sudo().search([('active', '=', True)])
            
            # Serializar datos
            bank_data = [
                {
                    "id": bank.id,
                    "name": bank.name,
                    "bic": bank.bic or "",
                    "active": bank.active
                }
                for bank in banks
            ]
            
            return self._success_response(bank_data)
            
        except Exception as e:
            _logger.error("Error getting banks: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    # ==================== ENDPOINTS DE CONFIGURACIÓN ====================
    
    @http.route('/api/collection/config/transaction-types', type='json', auth='user', methods=['GET'], csrf=False)
    def get_transaction_types(self, **kwargs):
        """Obtener tipos de transacción disponibles"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            transaction_types = [
                {"key": "movimiento_recaudacion", "label": "Acreditación"},
                {"key": "retiro", "label": "Mov. Retiro"},
                {"key": "movimiento_interno", "label": "Mov. Interno"}
            ]
            
            return self._success_response(transaction_types)
            
        except Exception as e:
            _logger.error("Error getting transaction types: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/config/transaction-states', type='json', auth='user', methods=['GET'], csrf=False)
    def get_transaction_states(self, **kwargs):
        """Obtener estados de transacción disponibles"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            transaction_states = [
                {"key": "aprobado", "label": "Aprobado"},
                {"key": "pendiente", "label": "Pendiente"},
                {"key": "rechazado", "label": "Rechazado"},
                {"key": "interno", "label": "Interno"}
            ]
            
            return self._success_response(transaction_states)
            
        except Exception as e:
            _logger.error("Error getting transaction states: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    # ==================== ENDPOINT DE ESTADÍSTICAS ====================
    
    @http.route('/api/collection/statistics', type='json', auth='user', methods=['GET'], csrf=False)
    def get_statistics(self, **kwargs):
        """Obtener estadísticas generales"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Contadores básicos
            stats = {
                "total_transactions": request.env['collection.transaction'].sudo().search_count([]),
                "total_customers": request.env['res.partner'].sudo().search_count([
                    ('check_origin_account', '!=', True),
                    ('customer_rank', '>', 0)
                ]),
                "total_services": request.env['collection.services.commission'].sudo().search_count([]),
                "pending_transactions": request.env['collection.transaction'].sudo().search_count([
                    ('transaction_state', '=', 'pendiente')
                ]),
                "approved_transactions": request.env['collection.transaction'].sudo().search_count([
                    ('transaction_state', '=', 'aprobado')
                ])
            }
            
            # Estadísticas por moneda
            currencies = request.env['res.currency'].sudo().search([('active', '=', True)])
            currency_stats = {}
            
            for currency in currencies:
                transactions = request.env['collection.transaction'].sudo().search([
                    ('currency_id', '=', currency.id)
                ])
                currency_stats[currency.name] = {
                    "count": len(transactions),
                    "total_amount": sum(t.amount for t in transactions)
                }
            
            stats["currency_stats"] = currency_stats
            
            return self._success_response(stats)
            
        except Exception as e:
            _logger.error("Error getting statistics: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
