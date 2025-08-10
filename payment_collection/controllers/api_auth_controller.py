# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from functools import wraps
import jwt
import logging
from datetime import datetime, timedelta
import secrets

_logger = logging.getLogger(__name__)


class APIAuthManager:
    """Gestor de autenticación para las APIs"""
    
    @staticmethod
    def generate_api_key():
        """Generar una nueva API key"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_api_key(api_key):
        """Validar una API key"""
        # Buscar en el modelo de API keys (deberías crear este modelo)
        api_key_record = request.env['collection.api.key'].sudo().search([
            ('key', '=', api_key),
            ('active', '=', True),
            ('expiry_date', '>', datetime.now())
        ], limit=1)
        
        if api_key_record:
            # Actualizar último uso
            api_key_record.last_used = datetime.now()
            return api_key_record.user_id
        
        return None
    
    @staticmethod
    def generate_jwt_token(user_id, expires_in_hours=24):
        """Generar un token JWT"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=expires_in_hours),
            'iat': datetime.utcnow()
        }
        
        # Obtener secret key desde configuración
        secret_key = request.env['ir.config_parameter'].sudo().get_param(
            'collection.jwt_secret_key', 'default-secret-key'
        )
        
        return jwt.encode(payload, secret_key, algorithm='HS256')
    
    @staticmethod
    def validate_jwt_token(token):
        """Validar un token JWT"""
        try:
            secret_key = request.env['ir.config_parameter'].sudo().get_param(
                'collection.jwt_secret_key', 'default-secret-key'
            )
            
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            user_id = payload.get('user_id')
            
            # Verificar que el usuario existe y está activo
            user = request.env['res.users'].sudo().browse(user_id)
            if user.exists() and user.active:
                return user
            
        except jwt.ExpiredSignatureError:
            _logger.warning("Expired JWT token")
        except jwt.InvalidTokenError:
            _logger.warning("Invalid JWT token")
        
        return None


def api_auth_required(auth_methods=['api_key', 'jwt', 'session']):
    """Decorador para requerir autenticación en endpoints de API"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            authenticated_user = None
            
            # Intentar autenticación por API Key
            if 'api_key' in auth_methods:
                auth_header = request.httprequest.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    api_key = auth_header[7:]  # Remover 'Bearer '
                    authenticated_user = APIAuthManager.validate_api_key(api_key)
                    
                    if authenticated_user:
                        # Establecer el usuario en el contexto
                        request.env.user = authenticated_user
            
            # Intentar autenticación por JWT
            if not authenticated_user and 'jwt' in auth_methods:
                auth_header = request.httprequest.headers.get('Authorization', '')
                if auth_header.startswith('JWT '):
                    token = auth_header[4:]  # Remover 'JWT '
                    authenticated_user = APIAuthManager.validate_jwt_token(token)
                    
                    if authenticated_user:
                        request.env.user = authenticated_user
            
            # Verificar autenticación de sesión (fallback)
            if not authenticated_user and 'session' in auth_methods:
                if not request.env.user or request.env.user._is_public():
                    authenticated_user = None
                else:
                    authenticated_user = request.env.user
            
            # Si no hay autenticación válida, retornar error
            if not authenticated_user:
                return {
                    "success": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Autenticación requerida"
                    }
                }
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limit(max_requests=100, window_minutes=60):
    """Decorador para limitar la velocidad de requests"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obtener identificador del usuario/IP
            user_id = request.env.user.id if request.env.user else None
            client_ip = request.httprequest.environ.get('REMOTE_ADDR')
            identifier = f"user_{user_id}" if user_id else f"ip_{client_ip}"
            
            # Verificar límite de velocidad
            # Aquí deberías implementar la lógica de rate limiting
            # usando Redis, Memcached o la base de datos
            
            # Por ahora, solo logeamos
            _logger.info(f"Rate limit check for {identifier}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


class CollectionAuthAPI(http.Controller):
    """API para gestión de autenticación"""
    
    @http.route('/api/collection/auth/login', type='json', auth='none', methods=['POST'], csrf=False)
    def login(self, **kwargs):
        """Endpoint de login para obtener tokens"""
        try:
            username = kwargs.get('username')
            password = kwargs.get('password')
            
            if not username or not password:
                return {
                    "success": False,
                    "error": {
                        "code": "MISSING_CREDENTIALS",
                        "message": "Username y password son requeridos"
                    }
                }
            
            # Autenticar usuario
            uid = request.session.authenticate(request.session.db, username, password)
            
            if uid:
                user = request.env['res.users'].sudo().browse(uid)
                
                # Generar tokens
                api_key = APIAuthManager.generate_api_key()
                jwt_token = APIAuthManager.generate_jwt_token(uid)
                
                # Crear registro de API key (opcional)
                # api_key_record = request.env['collection.api.key'].sudo().create({
                #     'user_id': uid,
                #     'key': api_key,
                #     'name': f'API Key for {user.name}',
                #     'expiry_date': datetime.now() + timedelta(days=30)
                # })
                
                return {
                    "success": True,
                    "data": {
                        "user_id": uid,
                        "username": user.login,
                        "name": user.name,
                        "api_key": api_key,
                        "jwt_token": jwt_token,
                        "expires_in": 24 * 3600,  # 24 horas en segundos
                        "token_type": "Bearer"
                    },
                    "message": "Login exitoso"
                }
            else:
                return {
                    "success": False,
                    "error": {
                        "code": "INVALID_CREDENTIALS",
                        "message": "Credenciales inválidas"
                    }
                }
                
        except Exception as e:
            _logger.error("Error in login: %s", str(e))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Error interno del servidor"
                }
            }
    
    @http.route('/api/collection/auth/refresh', type='json', auth='user', methods=['POST'], csrf=False)
    @api_auth_required()
    def refresh_token(self, **kwargs):
        """Renovar token JWT"""
        try:
            user_id = request.env.user.id
            new_jwt_token = APIAuthManager.generate_jwt_token(user_id)
            
            return {
                "success": True,
                "data": {
                    "jwt_token": new_jwt_token,
                    "expires_in": 24 * 3600,
                    "token_type": "Bearer"
                },
                "message": "Token renovado exitosamente"
            }
            
        except Exception as e:
            _logger.error("Error refreshing token: %s", str(e))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Error al renovar token"
                }
            }
    
    @http.route('/api/collection/auth/validate', type='json', auth='user', methods=['GET'], csrf=False)
    @api_auth_required()
    def validate_token(self, **kwargs):
        """Validar token actual"""
        try:
            user = request.env.user
            
            return {
                "success": True,
                "data": {
                    "valid": True,
                    "user_id": user.id,
                    "username": user.login,
                    "name": user.name,
                    "groups": [group.name for group in user.groups_id]
                },
                "message": "Token válido"
            }
            
        except Exception as e:
            _logger.error("Error validating token: %s", str(e))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Error al validar token"
                }
            }


# Ejemplo de uso del decorador en un endpoint
class SecureTransactionAPI(http.Controller):
    """Ejemplo de API con autenticación decorada"""
    
    @http.route('/api/collection/secure/transactions', type='json', auth='none', methods=['GET'], csrf=False)
    @api_auth_required(['api_key', 'jwt'])
    @rate_limit(max_requests=50, window_minutes=60)
    def get_secure_transactions(self, **kwargs):
        """Endpoint seguro para obtener transacciones"""
        try:
            # El usuario ya está autenticado por el decorador
            user = request.env.user
            
            # Verificar permisos específicos
            if not user.has_group('payment_collection.group_collection_user'):
                return {
                    "success": False,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": "No tiene permisos suficientes"
                    }
                }
            
            # Lógica del endpoint
            transactions = request.env['collection.transaction'].sudo().search([
                ('create_uid', '=', user.id)
            ], limit=kwargs.get('limit', 10))
            
            return {
                "success": True,
                "data": {
                    "transactions": [
                        {
                            "id": t.id,
                            "transaction_name": t.transaction_name,
                            "amount": t.amount,
                            "date": t.date.isoformat() if t.date else None
                        }
                        for t in transactions
                    ],
                    "count": len(transactions)
                }
            }
            
        except Exception as e:
            _logger.error("Error in secure endpoint: %s", str(e))
            return {
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Error interno del servidor"
                }
            }
