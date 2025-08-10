# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CollectionCustomersAPI(http.Controller):
    
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
    
    def _serialize_customer(self, customer):
        """Serializar un cliente para la API"""
        # Calcular saldos
        dashboard = request.env['collection.dashboard.customer'].sudo().search(
            [('customer', '=', customer.id)], limit=1
        )
        
        return {
            "id": customer.id,
            "name": customer.name,
            "vat": customer.vat or "",
            "email": customer.email or "",
            "phone": customer.phone or "",
            "is_company": customer.is_company,
            "active": customer.active,
            "total_balance": dashboard.customer_total_balance if dashboard else 0.0,
            "available_balance": dashboard.customer_available_balance if dashboard else 0.0,
            "real_balance": dashboard.customer_real_balance if dashboard else 0.0
        }
    
    def _calculate_balances(self, customer_id):
        """Calcular saldos de un cliente"""
        transactions = request.env['collection.transaction'].sudo().search([
            ('customer', '=', customer_id),
            ('collection_trans_type', '!=', 'movimiento_interno')
        ])
        
        total_balance = sum(t.amount for t in transactions)
        
        # Obtener saldos por moneda
        currencies = request.env['res.currency'].sudo().search([])
        currency_balances = {}
        
        for currency in currencies:
            currency_transactions = transactions.filtered(lambda t: t.currency_id.id == currency.id)
            currency_balances[currency.name] = sum(t.amount for t in currency_transactions)
        
        return {
            "total_balance": total_balance,
            "currency_balances": currency_balances
        }
    
    # ==================== ENDPOINTS DE CLIENTES ====================
    
    @http.route('/api/collection/customers', type='json', auth='user', methods=['GET'], csrf=False)
    def get_customers(self, **kwargs):
        """Obtener lista de clientes"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Construir dominio de búsqueda
            domain = [('check_origin_account', '!=', True)]
            
            if 'name' in kwargs and kwargs['name']:
                domain.append(('name', 'ilike', kwargs['name']))
            
            if 'vat' in kwargs and kwargs['vat']:
                domain.append(('vat', 'ilike', kwargs['vat']))
            
            if kwargs.get('active_only', True):
                domain.append(('active', '=', True))
            
            # Buscar clientes
            customers = request.env['res.partner'].sudo().search(domain)
            
            # Serializar datos
            customer_data = [self._serialize_customer(c) for c in customers]
            
            return self._success_response(customer_data)
            
        except Exception as e:
            _logger.error("Error getting customers: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/customers/<int:customer_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_customer_by_id(self, customer_id):
        """Obtener cliente por ID"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            customer = request.env['res.partner'].sudo().browse(customer_id)
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            return self._success_response(self._serialize_customer(customer))
            
        except Exception as e:
            _logger.error("Error getting customer %s: %s", customer_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/customers/<int:customer_id>/balance', type='json', auth='user', methods=['GET'], csrf=False)
    def get_customer_balance(self, customer_id):
        """Obtener saldos de cliente"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            customer = request.env['res.partner'].sudo().browse(customer_id)
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Obtener dashboard del cliente
            dashboard = request.env['collection.dashboard.customer'].sudo().search(
                [('customer', '=', customer_id)], limit=1
            )
            
            if dashboard:
                dashboard.update_available_balance()
            
            # Calcular saldos detallados
            balance_data = self._calculate_balances(customer_id)
            
            result = {
                "customer_id": customer_id,
                "balances": {
                    "total_balance": dashboard.customer_total_balance if dashboard else 0.0,
                    "available_balance": dashboard.customer_available_balance if dashboard else 0.0,
                    "real_balance": dashboard.customer_real_balance if dashboard else 0.0
                },
                "currency_balances": balance_data["currency_balances"],
                "last_updated": dashboard.write_date.isoformat() if dashboard and dashboard.write_date else None
            }
            
            return self._success_response(result)
            
        except Exception as e:
            _logger.error("Error getting customer balance %s: %s", customer_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/customers', type='json', auth='user', methods=['POST'], csrf=False)
    def create_customer(self, **kwargs):
        """Crear un nuevo cliente"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar datos requeridos
            if 'name' not in kwargs:
                return self._error_response(400, "MISSING_FIELD", "Campo requerido: name")
            
            # Preparar datos del cliente
            customer_data = {
                'name': kwargs['name'],
                'is_company': kwargs.get('is_company', True),
                'customer_rank': 1,
                'supplier_rank': 0,
                'email': kwargs.get('email', ''),
                'phone': kwargs.get('phone', ''),
                'vat': kwargs.get('vat', ''),
                'check_origin_account': False
            }
            
            # Crear el cliente
            customer = request.env['res.partner'].sudo().create(customer_data)
            
            return self._success_response({
                "id": customer.id,
                "name": customer.name,
                "vat": customer.vat
            }, "Cliente creado exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error creating customer: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/customers/<int:customer_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_customer(self, customer_id, **kwargs):
        """Actualizar cliente"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            customer = request.env['res.partner'].sudo().browse(customer_id)
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Campos permitidos para actualizar
            allowed_fields = ['name', 'email', 'phone', 'vat', 'is_company']
            
            update_data = {}
            updated_fields = []
            
            for field in allowed_fields:
                if field in kwargs:
                    update_data[field] = kwargs[field]
                    updated_fields.append(field)
            
            if update_data:
                customer.write(update_data)
            
            return self._success_response({
                "id": customer.id,
                "updated_fields": updated_fields
            }, "Cliente actualizado exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error updating customer %s: %s", customer_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/customers/<int:customer_id>/transactions', type='json', auth='user', methods=['GET'], csrf=False)
    def get_customer_transactions(self, customer_id, **kwargs):
        """Obtener transacciones de un cliente"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            customer = request.env['res.partner'].sudo().browse(customer_id)
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Construir dominio de búsqueda
            domain = [('customer', '=', customer_id)]
            
            if 'date_from' in kwargs:
                domain.append(('date', '>=', kwargs['date_from']))
            
            if 'date_to' in kwargs:
                domain.append(('date', '<=', kwargs['date_to']))
            
            if 'transaction_state' in kwargs:
                domain.append(('transaction_state', '=', kwargs['transaction_state']))
            
            # Paginación
            limit = kwargs.get('limit', 50)
            offset = kwargs.get('offset', 0)
            
            # Buscar transacciones
            transactions = request.env['collection.transaction'].sudo().search(
                domain, limit=limit, offset=offset, order='date desc'
            )
            
            # Contar total
            total_count = request.env['collection.transaction'].sudo().search_count(domain)
            
            # Serializar datos básicos de transacciones
            transaction_data = []
            for t in transactions:
                transaction_data.append({
                    "id": t.id,
                    "transaction_name": t.transaction_name,
                    "amount": t.amount,
                    "date": t.date.isoformat() if t.date else None,
                    "collection_trans_type": t.collection_trans_type,
                    "transaction_state": t.transaction_state,
                    "description": t.description or ""
                })
            
            return self._success_response({
                "customer_id": customer_id,
                "transactions": transaction_data,
                "total_count": total_count,
                "has_next": total_count > (offset + limit)
            })
            
        except Exception as e:
            _logger.error("Error getting customer transactions %s: %s", customer_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
