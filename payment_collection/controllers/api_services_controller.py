# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import json
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CollectionServicesAPI(http.Controller):
    
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
    
    def _serialize_service(self, service):
        """Serializar un servicio para la API"""
        return {
            "id": service.id,
            "customer": {
                "id": service.customer.id,
                "name": service.customer.name,
                "vat": service.customer.vat or ""
            } if service.customer else None,
            "service": {
                "id": service.services.id,
                "name": service.services.name,
                "type": getattr(service.services, 'collection_type', 'service')
            } if service.services else None,
            "commission": service.commission,
            "commission_app_rate": service.commission_app_rate,
            "name_account": service.name_account or "",
            "bank": {
                "id": service.bank_id.id,
                "name": service.bank_id.name
            } if service.bank_id else None,
            "cbu": service.cbu or "",
            "cvu": service.cvu or "",
            "alias": service.alias or "",
            "cuit": service.cuit or "",
            "agent_commissions": [
                {
                    "agent_id": agent.agent.id,
                    "agent_name": agent.agent.name,
                    "commission_rate": agent.commission_rate
                }
                for agent in service.agent_services_commission
            ]
        }
    
    # ==================== ENDPOINTS DE SERVICIOS ====================
    
    @http.route('/api/collection/services', type='json', auth='user', methods=['GET'], csrf=False)
    def get_services(self, **kwargs):
        """Obtener lista de servicios"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Construir dominio de búsqueda
            domain = []
            
            if 'customer_id' in kwargs:
                domain.append(('customer', '=', kwargs['customer_id']))
            
            # Buscar servicios
            services = request.env['collection.services.commission'].sudo().search(domain)
            
            # Serializar datos
            service_data = [self._serialize_service(s) for s in services]
            
            return self._success_response(service_data)
            
        except Exception as e:
            _logger.error("Error getting services: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/services', type='json', auth='user', methods=['POST'], csrf=False)
    def create_service(self, **kwargs):
        """Crear un nuevo servicio"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            # Validar datos requeridos
            required_fields = ['customer_id', 'service_id', 'commission']
            for field in required_fields:
                if field not in kwargs:
                    return self._error_response(400, "MISSING_FIELD", f"Campo requerido: {field}")
            
            # Validar cliente
            customer = request.env['res.partner'].sudo().browse(kwargs['customer_id'])
            if not customer.exists():
                return self._error_response(404, "CUSTOMER_NOT_FOUND", "Cliente no encontrado")
            
            # Validar servicio
            service_product = request.env['product.template'].sudo().browse(kwargs['service_id'])
            if not service_product.exists():
                return self._error_response(404, "SERVICE_NOT_FOUND", "Servicio no encontrado")
            
            # Preparar datos del servicio
            service_data = {
                'customer': kwargs['customer_id'],
                'services': kwargs['service_id'],
                'commission': kwargs['commission'],
                'commission_app_rate': kwargs.get('commission_app_rate', 0.0),
                'name_account': kwargs.get('name_account', ''),
                'cbu': kwargs.get('cbu', ''),
                'cvu': kwargs.get('cvu', ''),
                'alias': kwargs.get('alias', ''),
                'cuit': kwargs.get('cuit', '')
            }
            
            if 'bank_id' in kwargs:
                bank = request.env['res.bank'].sudo().browse(kwargs['bank_id'])
                if bank.exists():
                    service_data['bank_id'] = bank.id
            
            # Crear el servicio
            service = request.env['collection.services.commission'].sudo().create(service_data)
            
            # Crear comisiones de agentes si se proporcionan
            if 'agent_commissions' in kwargs and kwargs['agent_commissions']:
                for agent_comm in kwargs['agent_commissions']:
                    agent = request.env['res.partner'].sudo().browse(agent_comm['agent_id'])
                    if agent.exists():
                        agent_service_data = {
                            'collection_services_commission_id': service.id,
                            'agent': agent.id,
                            'commission_rate': agent_comm['commission_rate']
                        }
                        request.env['agent.commission.service'].sudo().create(agent_service_data)
            
            return self._success_response({
                "id": service.id,
                "name_account": service.name_account
            }, "Servicio creado exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error creating service: %s", str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/services/<int:service_id>', type='json', auth='user', methods=['GET'], csrf=False)
    def get_service_by_id(self, service_id):
        """Obtener servicio por ID"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            service = request.env['collection.services.commission'].sudo().browse(service_id)
            if not service.exists():
                return self._error_response(404, "SERVICE_NOT_FOUND", "Servicio no encontrado")
            
            return self._success_response(self._serialize_service(service))
            
        except Exception as e:
            _logger.error("Error getting service %s: %s", service_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/services/<int:service_id>', type='json', auth='user', methods=['PUT'], csrf=False)
    def update_service(self, service_id, **kwargs):
        """Actualizar servicio"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            service = request.env['collection.services.commission'].sudo().browse(service_id)
            if not service.exists():
                return self._error_response(404, "SERVICE_NOT_FOUND", "Servicio no encontrado")
            
            # Campos permitidos para actualizar
            allowed_fields = [
                'commission', 'commission_app_rate', 'name_account',
                'cbu', 'cvu', 'alias', 'cuit', 'bank_id'
            ]
            
            update_data = {}
            updated_fields = []
            
            for field in allowed_fields:
                if field in kwargs:
                    if field == 'bank_id' and kwargs[field]:
                        bank = request.env['res.bank'].sudo().browse(kwargs[field])
                        if bank.exists():
                            update_data[field] = bank.id
                            updated_fields.append(field)
                    else:
                        update_data[field] = kwargs[field]
                        updated_fields.append(field)
            
            if update_data:
                service.write(update_data)
            
            return self._success_response({
                "id": service.id,
                "updated_fields": updated_fields
            }, "Servicio actualizado exitosamente")
            
        except ValidationError as e:
            return self._error_response(422, "VALIDATION_ERROR", str(e))
        except Exception as e:
            _logger.error("Error updating service %s: %s", service_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    
    @http.route('/api/collection/services/<int:service_id>', type='json', auth='user', methods=['DELETE'], csrf=False)
    def delete_service(self, service_id):
        """Eliminar servicio"""
        try:
            auth_error = self._validate_auth()
            if auth_error:
                return auth_error
            
            service = request.env['collection.services.commission'].sudo().browse(service_id)
            if not service.exists():
                return self._error_response(404, "SERVICE_NOT_FOUND", "Servicio no encontrado")
            
            service.unlink()
            
            return self._success_response({}, "Servicio eliminado exitosamente")
            
        except Exception as e:
            _logger.error("Error deleting service %s: %s", service_id, str(e))
            return self._error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
