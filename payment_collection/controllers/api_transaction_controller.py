# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from datetime import datetime
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class CollectionTransactionAPI(http.Controller):
    
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
    
    def _serialize_transaction(self, transaction):
        """Serializar una transacción para la API"""
        return {
            "id": transaction.id,
            "transaction_name": transaction.transaction_name,
            "customer": {
                "id": transaction.customer.id,
                "name": transaction.customer.name,
                "vat": transaction.customer.vat or "",
                "email": transaction.customer.email or ""
            } if transaction.customer else None,
            "amount": transaction.amount,
            "currency": {
                "id": transaction.currency_id.id,
                "name": transaction.currency_id.name,
                "symbol": transaction.currency_id.symbol
            } if transaction.currency_id else None,
            "date": transaction.date.isoformat() if transaction.date else None,
            "collection_trans_type": transaction.collection_trans_type,
            "transaction_state": transaction.transaction_state,
            "service": {
                "id": transaction.service.id,
                "name": transaction.service.name_account,
                "commission": transaction.service.commission,
                "commission_app_rate": transaction.service.commission_app_rate
            } if transaction.service else None,
            "operation": {
                "id": transaction.operation.id,
                "name": transaction.operation.name
            } if transaction.operation else None,
            "commission": transaction.commission,
            "commission_amount": transaction.commission_app_amount,
            "description": transaction.description or "",
            "origin_account": self._serialize_origin_account(transaction),
            "destination_account": self._serialize_destination_account(transaction),
            "balances": {
                "real_balance": transaction.real_balance,
                "available_balance": transaction.available_balance,
                "total_balance": transaction.total_balance_customer
            },
            "categories": [
                {"id": cat.id, "name": cat.name} 
                for cat in transaction.categories
            ],
            "is_commission": transaction.is_commission,
            "is_concilied": transaction.is_concilied,
            "created_at": transaction.create_date.isoformat() if transaction.create_date else None,
            "updated_at": transaction.write_date.isoformat() if transaction.write_date else None
        }
    
    def _serialize_origin_account(self, transaction):
        """Serializar cuenta origen"""
        if transaction.origin_type == 'externo':
            return {
                "type": "externo",
                "cuit": transaction.origin_account_cuit or "",
                "cbu": transaction.origin_account_cbu or "",
                "cvu": transaction.origin_account_cvu or "",
                "alias": transaction.alias_origen or "",
                "name": transaction.origen_name_account_extern or ""
            }
        else:
            return {
                "type": "interno",
                "id": transaction.origin_account.id if transaction.origin_account else None,
                "name": transaction.origin_account.name_account if transaction.origin_account else "",
                "cuit": transaction.origin_account.cuit if transaction.origin_account else "",
                "cbu": transaction.origin_account.cbu if transaction.origin_account else "",
                "cvu": transaction.origin_account.cvu if transaction.origin_account else "",
                "alias": transaction.origin_account.alias if transaction.origin_account else ""
            }
    
    def _serialize_destination_account(self, transaction):
        """Serializar cuenta destino"""
        return {
            "cuit": transaction.cuit_destination_account or "",
            "cbu": transaction.cbu_destination_account or "",
            "cvu": transaction.cvu_destination_account or "",
            "alias": transaction.alias_destination_account or "",
            "name": transaction.name_destination_account or ""
        }
    
    # ==================== ENDPOINTS DE TRANSACCIONES ====================
    
    @http.route('/api/collection/transactions', type='json', auth='user', methods=['POST'], csrf=False)
    def create_transaction(self, **kwargs):
        """Crear una nueva transacción"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar datos requeridos
            required_fields = ['customer_id', 'amount', 'collection_trans_type']
            for field in required_fields:
                if field not in kwargs:
                    return self._error_response(400, "MISSING_FIELD", f"Campo requerido: {field}")
            
            # Validar cliente
            customer = request.env['res.partner'].sudo().browse(kwargs['customer_id'])
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Preparar datos de la transacción
            transaction_data = {
                'customer': kwargs['customer_id'],
                'amount': kwargs['amount'],
                'collection_trans_type': kwargs['collection_trans_type'],
                'date': kwargs.get('date', datetime.now().date()),
                'description': kwargs.get('description', ''),
                'count': 0
            }
            
            # Campos opcionales
            if 'service_id' in kwargs:
                service = request.env['collection.services.commission'].sudo().browse(kwargs['service_id'])
                if service.exists():
                    transaction_data['service'] = service.id
                    transaction_data['commission'] = service.commission
            
            if 'operation_id' in kwargs:
                operation = request.env['product.template'].sudo().browse(kwargs['operation_id'])
                if operation.exists():
                    transaction_data['operation'] = operation.id
            
            if 'currency_id' in kwargs:
                currency = request.env['res.currency'].sudo().browse(kwargs['currency_id'])
                if currency.exists():
                    transaction_data['currency_id'] = currency.id
            
            if 'commission' in kwargs:
                transaction_data['commission'] = kwargs['commission']
            
            # Datos de cuenta origen
            if 'origin_account' in kwargs:
                origin = kwargs['origin_account']
                transaction_data.update({
                    'origin_type': kwargs.get('origin_type', 'externo'),
                    'origin_account_cuit': origin.get('cuit', ''),
                    'origin_account_cbu': origin.get('cbu', ''),
                    'origin_account_cvu': origin.get('cvu', ''),
                    'alias_origen': origin.get('alias', ''),
                    'origen_name_account_extern': origin.get('name', '')
                })
            
            # Datos de cuenta destino
            if 'destination_account' in kwargs:
                dest = kwargs['destination_account']
                transaction_data.update({
                    'cuit_destination_account': dest.get('cuit', ''),
                    'cbu_destination_account': dest.get('cbu', ''),
                    'cvu_destination_account': dest.get('cvu', ''),
                    'alias_destination_account': dest.get('alias', ''),
                    'name_destination_account': dest.get('name', '')
                })
            
            # Crear la transacción
            transaction = request.env['collection.transaction'].sudo().create(transaction_data)
            
            # Asignar categorías si se proporcionan
            if 'categories' in kwargs and kwargs['categories']:
                categories = request.env['collection.category'].sudo().browse(kwargs['categories'])
                transaction.categories = [(6, 0, categories.ids)]
            
            return self._success_response({
                "id": transaction.id,
                "transaction_name": transaction.transaction_name,
                "status": transaction.transaction_state,
                "commission_amount": transaction.commission_app_amount,
                "real_balance": transaction.real_balance,
                "available_balance": transaction.available_balance
            }, "Transacción creada exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error(f"Error creating transaction: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/transactions', type='json', auth='user', methods=['GET'], csrf=False)
    def get_transactions(self, **kwargs):
        """Obtener lista de transacciones"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Construir dominio de búsqueda
            domain = []
            
            if 'customer_id' in kwargs:
                domain.append(('customer', '=', kwargs['customer_id']))
            
            if 'date_from' in kwargs:
                domain.append(('date', '>=', kwargs['date_from']))
            
            if 'date_to' in kwargs:
                domain.append(('date', '<=', kwargs['date_to']))
            
            if 'transaction_state' in kwargs:
                domain.append(('transaction_state', '=', kwargs['transaction_state']))
            
            if 'collection_trans_type' in kwargs:
                domain.append(('collection_trans_type', '=', kwargs['collection_trans_type']))
            
            # Paginación
            limit = kwargs.get('limit', 50)
            offset = kwargs.get('offset', 0)
            
            # Buscar transacciones
            transactions = request.env['collection.transaction'].sudo().search(
                domain, limit=limit, offset=offset, order='id desc'
            )
            
            # Contar total
            total_count = request.env['collection.transaction'].sudo().search_count(domain)
            
            # Serializar datos
            transaction_data = [self._serialize_transaction(t) for t in transactions]
            
            return self._success_response({
                "transactions": transaction_data,
                "total_count": total_count,
                "has_next": total_count > (offset + limit)
            })
            
        except Exception as e:
            _logger.error(f"Error getting transactions: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/transactions/<int:transaction_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_transaction_by_id(self, transaction_id, **kwargs):
        """Obtener transacción por ID"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            transaction = request.env['collection.transaction'].sudo().browse(transaction_id)
            if not transaction.exists():
                return self._error_response(404, "TRANSACTION_NOT_FOUND", "Transacción no encontrada")
            
            return self._success_response(self._serialize_transaction(transaction))
            
        except Exception as e:
            _logger.error(f"Error getting transaction {transaction_id}: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/transactions/<int:transaction_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_transaction(self, transaction_id, **kwargs):
        """Actualizar transacción"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            transaction = request.env['collection.transaction'].sudo().browse(transaction_id)
            if not transaction.exists():
                return self._error_response(404, "TRANSACTION_NOT_FOUND", "Transacción no encontrada")
            
            # Campos permitidos para actualizar
            allowed_fields = [
                'amount', 'description', 'transaction_state', 'commission',
                'date', 'commission_app_rate'
            ]
            
            update_data = {}
            updated_fields = []
            
            for field in allowed_fields:
                if field in kwargs:
                    update_data[field] = kwargs[field]
                    updated_fields.append(field)
            
            if update_data:
                transaction.write(update_data)
            
            return self._success_response({
                "id": transaction.id,
                "updated_fields": updated_fields,
                "new_commission_amount": transaction.commission_app_amount if 'amount' in updated_fields or 'commission' in updated_fields else None
            }, "Transacción actualizada exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error(f"Error updating transaction {transaction_id}: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/transactions/<int:transaction_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_transaction(self, transaction_id, **kwargs):
        """Eliminar transacción"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            transaction = request.env['collection.transaction'].sudo().browse(transaction_id)
            if not transaction.exists():
                return self._error_response(404, "TRANSACTION_NOT_FOUND", "Transacción no encontrada")
            
            transaction.unlink()
            
            return self._success_response({}, "Transacción eliminada exitosamente")
            
        except UserError as e:
            return self._error_response(422, "DELETE_ERROR", str(e))
        except Exception as e:
            _logger.error(f"Error deleting transaction {transaction_id}: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/transactions/<int:transaction_id>/status', type='json', auth='user', methods=['PATCH'], csrf=False)
    def update_transaction_status(self, transaction_id, **kwargs):
        """Cambiar estado de transacción"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            if 'transaction_state' not in kwargs:
                return self._error_response(400, "MISSING_FIELD", "Campo requerido: transaction_state")
            
            transaction = request.env['collection.transaction'].sudo().browse(transaction_id)
            if not transaction.exists():
                return self._error_response(404, "TRANSACTION_NOT_FOUND", "Transacción no encontrada")
            
            previous_state = transaction.transaction_state
            transaction.transaction_state = kwargs['transaction_state']
            
            return self._success_response({
                "id": transaction.id,
                "previous_state": previous_state,
                "new_state": transaction.transaction_state
            }, "Estado actualizado exitosamente")
            
        except Exception as e:
            _logger.error(f"Error updating transaction status {transaction_id}: {str(e)}")
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
