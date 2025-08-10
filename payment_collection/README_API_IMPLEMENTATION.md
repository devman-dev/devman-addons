# Collection Transaction API - Guía de Implementación

## Resumen

Este documento proporciona una guía completa para implementar e integrar las APIs del módulo de transacciones comerciales de Odoo. El módulo incluye endpoints RESTful para gestionar transacciones, clientes, servicios, reportes y más.

## Tabla de Contenidos

1. [Archivos Creados](#archivos-creados)
2. [Estructura de la API](#estructura-de-la-api)
3. [Instalación y Configuración](#instalación-y-configuración)
4. [Autenticación](#autenticación)
5. [Endpoints Disponibles](#endpoints-disponibles)
6. [Ejemplos de Integración](#ejemplos-de-integración)
7. [Seguridad](#seguridad)
8. [Testing](#testing)
9. [Deployment](#deployment)
10. [Troubleshooting](#troubleshooting)

## Archivos Creados

### Documentación
- `api_documentation.md` - Documentación completa de la API
- `integration_examples.md` - Ejemplos de código en múltiples lenguajes
- `README_API_IMPLEMENTATION.md` - Este archivo

### Controladores de API
- `controllers/api_transaction_controller.py` - API para transacciones
- `controllers/api_services_controller.py` - API para servicios
- `controllers/api_customers_controller.py` - API para clientes
- `controllers/api_utils_controller.py` - API para utilidades (operaciones, categorías, etc.)
- `controllers/api_reports_controller.py` - API para reportes y analytics
- `controllers/api_auth_controller.py` - API para autenticación y seguridad

## Estructura de la API

### Base URL
```
https://tu-instancia-odoo.com/api/collection/
```

### Endpoints Principales

#### Transacciones
- `POST /transactions` - Crear transacción
- `GET /transactions` - Listar transacciones
- `GET /transactions/{id}` - Obtener transacción específica
- `PUT /transactions/{id}` - Actualizar transacción
- `DELETE /transactions/{id}` - Eliminar transacción
- `PATCH /transactions/{id}/status` - Cambiar estado

#### Clientes
- `GET /customers` - Listar clientes
- `GET /customers/{id}` - Obtener cliente específico
- `GET /customers/{id}/balance` - Obtener saldos del cliente
- `POST /customers` - Crear cliente
- `PUT /customers/{id}` - Actualizar cliente
- `GET /customers/{id}/transactions` - Transacciones del cliente

#### Servicios
- `GET /services` - Listar servicios
- `POST /services` - Crear servicio
- `GET /services/{id}` - Obtener servicio específico
- `PUT /services/{id}` - Actualizar servicio
- `DELETE /services/{id}` - Eliminar servicio

#### Reportes
- `POST /reports/transactions` - Generar reporte de transacciones
- `GET /reports/balance-summary` - Resumen de saldos
- `GET /reports/transaction-analytics` - Analytics de transacciones
- `GET /reports/commission-summary` - Resumen de comisiones

#### Utilidades
- `GET /operations` - Listar operaciones
- `GET /categories` - Listar categorías
- `GET /currencies` - Listar monedas
- `GET /banks` - Listar bancos
- `GET /config/transaction-types` - Tipos de transacción
- `GET /config/transaction-states` - Estados de transacción
- `GET /statistics` - Estadísticas generales

#### Autenticación
- `POST /auth/login` - Login para obtener tokens
- `POST /auth/refresh` - Renovar token JWT
- `GET /auth/validate` - Validar token actual

## Instalación y Configuración

### 1. Actualizar el módulo Odoo

Asegúrate de que todos los archivos estén en su lugar:

```bash
# Estructura esperada
payment_collection/
├── controllers/
│   ├── __init__.py
│   ├── api_transaction_controller.py
│   ├── api_services_controller.py
│   ├── api_customers_controller.py
│   ├── api_utils_controller.py
│   ├── api_reports_controller.py
│   ├── api_auth_controller.py
│   └── [controladores existentes...]
├── models/
│   └── [modelos existentes...]
├── api_documentation.md
├── integration_examples.md
└── README_API_IMPLEMENTATION.md
```

### 2. Reiniciar el servidor Odoo

```bash
# Reiniciar con actualización del módulo
./odoo-bin -u payment_collection -d tu_base_de_datos
```

### 3. Configurar parámetros del sistema

Ir a `Configuración > Parámetros del Sistema` y agregar:

```
collection.jwt_secret_key = tu-clave-secreta-jwt-muy-segura
collection.api_rate_limit = 1000
collection.api_rate_window = 3600
```

### 4. Configurar grupos de usuarios

Crear o verificar los grupos de seguridad:
- `payment_collection.group_collection_user` - Usuario básico
- `payment_collection.group_collection_manager` - Gestor
- `payment_collection.group_collection_admin` - Administrador

## Autenticación

### Métodos Soportados

1. **API Key** (Recomendado para servicios)
   ```
   Authorization: Bearer your-api-key-here
   ```

2. **JWT Token** (Recomendado para aplicaciones web/móviles)
   ```
   Authorization: JWT your-jwt-token-here
   ```

3. **Sesión de Odoo** (Para uso interno)
   - Usar autenticación estándar de Odoo

### Obtener Tokens

```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tu_usuario",
    "password": "tu_contraseña"
  }'
```

Respuesta:
```json
{
  "success": true,
  "data": {
    "user_id": 123,
    "username": "usuario",
    "name": "Nombre Usuario",
    "api_key": "abc123...",
    "jwt_token": "eyJ0eXAi...",
    "expires_in": 86400,
    "token_type": "Bearer"
  }
}
```

## Ejemplos de Uso Rápido

### Crear una Transacción

```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 123,
    "amount": 1000.50,
    "date": "2025-08-03",
    "collection_trans_type": "movimiento_recaudacion",
    "service_id": 45,
    "description": "Pago de servicios"
  }'
```

### Consultar Saldo de Cliente

```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/customers/123/balance \
  -H "Authorization: Bearer your-api-key"
```

### Obtener Analytics

```bash
curl -X GET "https://tu-instancia-odoo.com/api/collection/reports/transaction-analytics?date_from=2025-07-01&date_to=2025-08-03" \
  -H "Authorization: Bearer your-api-key"
```

## Seguridad

### Rate Limiting

- 1000 requests por hora por API key (configurable)
- 100 requests por minuto por IP

### Validaciones

- Todos los endpoints validan autenticación
- Validación de permisos por grupos de usuarios
- Validación de datos de entrada
- Sanitización de parámetros

### Headers de Seguridad

```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
```

## Testing

### Testing Básico

```python
import requests

# Configuración
base_url = "https://tu-instancia-odoo.com"
api_key = "your-api-key"
headers = {"Authorization": f"Bearer {api_key}"}

# Test de conectividad
response = requests.get(f"{base_url}/api/collection/statistics", headers=headers)
assert response.status_code == 200
print("✅ API funcionando correctamente")

# Test de creación de transacción
transaction_data = {
    "customer_id": 123,
    "amount": 100.0,
    "collection_trans_type": "movimiento_recaudacion"
}

response = requests.post(
    f"{base_url}/api/collection/transactions",
    json=transaction_data,
    headers=headers
)

if response.status_code == 200:
    print("✅ Transacción creada exitosamente")
else:
    print(f"❌ Error: {response.json()}")
```

### Testing Completo

```bash
# Usar pytest para testing automatizado
pip install pytest requests

# Crear archivo test_api.py
pytest test_api.py -v
```

## Deployment

### Configuración de Producción

1. **Variables de Entorno**
   ```bash
   export ODOO_JWT_SECRET_KEY="clave-super-secreta-produccion"
   export ODOO_API_RATE_LIMIT="5000"
   export ODOO_DB_NAME="produccion_db"
   ```

2. **Proxy Reverso (Nginx)**
   ```nginx
   location /api/collection/ {
       proxy_pass http://localhost:8069;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       
       # Rate limiting
       limit_req zone=api burst=10 nodelay;
   }
   ```

3. **SSL/TLS**
   - Usar certificados SSL válidos
   - Forzar HTTPS para todas las APIs
   - Configurar HSTS headers

### Monitoring

```python
# Agregar logging personalizado
import logging

# Configurar logger para APIs
api_logger = logging.getLogger('odoo.collection.api')
api_logger.setLevel(logging.INFO)

# Métricas importantes a monitorear:
# - Tiempo de respuesta de APIs
# - Tasa de errores
# - Uso por endpoint
# - Rate limiting triggers
```

## Troubleshooting

### Errores Comunes

#### 1. Error 401 - Unauthorized
```
Solución:
- Verificar que el API key sea válido
- Verificar que el usuario tenga permisos
- Verificar que el token no haya expirado
```

#### 2. Error 404 - Not Found
```
Solución:
- Verificar que la URL sea correcta
- Verificar que el endpoint esté habilitado
- Verificar que el módulo esté instalado
```

#### 3. Error 422 - Validation Error
```
Solución:
- Verificar que todos los campos requeridos estén presentes
- Verificar tipos de datos
- Verificar restricciones de dominio
```

#### 4. Error 500 - Internal Server Error
```
Solución:
- Revisar logs de Odoo
- Verificar configuración de base de datos
- Verificar permisos de archivos
```

### Debug Mode

```python
# Habilitar modo debug en controladores
import logging
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

# En los endpoints, agregar:
_logger.debug(f"Request data: {kwargs}")
_logger.debug(f"User: {request.env.user.name}")
```

### Logs Importantes

```bash
# Logs de Odoo
tail -f /var/log/odoo/odoo.log

# Filtrar logs de API
grep "collection.api" /var/log/odoo/odoo.log

# Monitorear requests
grep "POST\|GET\|PUT\|DELETE" /var/log/nginx/access.log | grep "/api/collection"
```

## Próximos Pasos

1. **Implementar Rate Limiting Avanzado**
   - Usar Redis para rate limiting distribuido
   - Diferentes límites por tipo de usuario

2. **Agregar Webhooks**
   - Notificaciones en tiempo real
   - Integración con sistemas externos

3. **Métricas y Analytics**
   - Dashboard de uso de API
   - Alertas automáticas

4. **Versionado de API**
   - Implementar v1, v2, etc.
   - Deprecation warnings

5. **Cache**
   - Implementar cache para consultas frecuentes
   - Cache de autenticación

## Contacto y Soporte

Para preguntas técnicas sobre la implementación:
- Revisar la documentación completa en `api_documentation.md`
- Ver ejemplos prácticos en `integration_examples.md`
- Revisar issues conocidos en este documento

## Changelog

### v1.0.0 (2025-08-03)
- ✅ Implementación inicial de todas las APIs
- ✅ Sistema de autenticación completo
- ✅ Documentación completa
- ✅ Ejemplos en múltiples lenguajes
- ✅ Sistema de seguridad básico

### Próxima versión (v1.1.0)
- 🔄 Rate limiting avanzado
- 🔄 Webhooks
- 🔄 Cache distribuido
- 🔄 Métricas avanzadas
