# API Documentation - Collection Transaction Module

## Introducción

Esta documentación describe todas las interfaces de API disponibles para integrar con el módulo de transacciones comerciales de Odoo. El módulo maneja transacciones de recaudación, retiros y movimientos internos.

## Autenticación

Todas las APIs requieren autenticación. Se recomienda usar:
- **API Key**: Para integraciones de servicios
- **Basic Auth**: Para aplicaciones web
- **OAuth**: Para aplicaciones móviles

### Headers requeridos
```
Content-Type: application/json
Authorization: Bearer {token}
```

## Base URL
```
https://tu-instancia-odoo.com/api/collection/
```

## Referencia de Tipos de Datos y Campos

### Campos Enumerados (Selection Fields)

#### Estados de Transacción (`transaction_state`)
| Valor | Descripción |
|-------|-------------|
| `"aprobado"` | Transacción aprobada y procesada |
| `"pendiente"` | Transacción pendiente de aprobación |
| `"rechazado"` | Transacción rechazada |
| `"interno"` | Transacción interna del sistema |

#### Tipos de Transacción (`collection_trans_type`)
| Valor | Descripción |
|-------|-------------|
| `"movimiento_recaudacion"` | Acreditación/Ingreso de fondos |
| `"retiro"` | Retiro/Débito de fondos |
| `"movimiento_interno"` | Transferencia entre cuentas internas |

#### Tipos de Origen (`origin_type`)
| Valor | Descripción |
|-------|-------------|
| `"externo"` | Origen externo al sistema |
| `"interno"` | Origen interno del sistema |

#### Formatos de Reporte (`format`)
| Valor | Descripción |
|-------|-------------|
| `"pdf"` | Archivo PDF |
| `"excel"` | Archivo Excel (.xlsx) |
| `"csv"` | Archivo CSV |

### Campos de Referencia (Foreign Keys)

#### IDs que requieren endpoints de referencia
| Campo | Endpoint de Referencia | Descripción |
|-------|----------------------|-------------|
| `customer_id` | `/customers` | ID del cliente (res.partner) |
| `service_id` | `/operations` | ID del servicio/operación (product.template) |
| `operation_id` | `/operations` | ID de la operación (product.template) |
| `currency_id` | `/currencies` | ID de la moneda (res.currency) |
| `bank_id` | `/banks` | ID del banco (res.bank) |
| `agent_id` | `/customers` | ID del agente (res.partner) |
| `customer_destination` | `/customers` | ID del cliente destino (res.partner) |
| `categories` | `/categories` | IDs de categorías (collection.category) |

### Formatos de Datos

#### Formatos de Fecha
- **Formato**: `"YYYY-MM-DD"`
- **Ejemplo**: `"2025-08-03"`

#### Formatos de Cuenta Bancaria
- **CUIT/CUIL**: 11 dígitos numéricos (ej: `"20123456789"`)
- **CBU**: 22 dígitos numéricos (ej: `"0123456789012345678901"`)
- **CVU**: 22 dígitos numéricos (ej: `"0000003100012345678912"`)
- **Alias**: Texto alfanumérico con puntos (ej: `"mi.alias.banco"`)

#### Tipos de Datos Básicos
- **Integer**: Número entero
- **Float**: Número decimal
- **String**: Cadena de texto
- **Boolean**: `true` o `false`
- **Array**: Lista de elementos

---

## 1. Endpoints de Transacciones

### 1.1 Crear Transacción
**POST** `/transactions`

Crea una nueva transacción comercial.

#### cURL Example
```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "amount": 1000.50,
    "date": "2025-08-03",
    "collection_trans_type": "movimiento_recaudacion",
    "service_id": 45,
    "operation_id": 67,
    "description": "Pago de servicios",
    "currency_id": 1,
    "origin_type": "externo",
    "origin_account": {
      "cuit": "20123456789",
      "cbu": "0123456789012345678901",
      "cvu": "0000003100012345678912",
      "alias": "mi.alias.banco",
      "name": "Cuenta Origen Externa"
    },
    "destination_account": {
      "cuit": "27987654321",
      "cbu": "9876543210987654321098",
      "cvu": "0000003100098765432198",
      "alias": "destino.alias",
      "name": "Cuenta Destino"
    },
    "commission": 2.5,
    "categories": [1, 2, 3]
  }'
```

#### Parámetros de Request

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `customer_id` | Integer | ✅ | ID del cliente | Referencia: Usar endpoint `/customers` |
| `amount` | Float | ✅ | Monto de la transacción | Valor numérico (positivo para acreditaciones, negativo para débitos) |
| `date` | String | ✅ | Fecha de la transacción | Formato: "YYYY-MM-DD" |
| `collection_trans_type` | String | ✅ | Tipo de transacción | `"movimiento_recaudacion"`, `"retiro"`, `"movimiento_interno"` |
| `service_id` | Integer | ❌ | ID del servicio | Referencia: Usar endpoint `/services` |
| `operation_id` | Integer | ❌ | ID de la operación | Referencia: Usar endpoint `/operations` |
| `description` | String | ❌ | Descripción de la transacción | Texto libre (máx 500 caracteres) |
| `currency_id` | Integer | ❌ | ID de la moneda | Referencia: Usar endpoint `/currencies` (default: moneda base) |
| `origin_type` | String | ❌ | Tipo de origen | `"externo"`, `"interno"` |
| `customer_destination` | Integer | ❌ | Cliente destino (para mov. internos) | Referencia: Usar endpoint `/customers` |
| `commission` | Float | ❌ | Comisión específica | Valor numérico (sobrescribe comisión del servicio) |
| `categories` | Array[Integer] | ❌ | IDs de categorías | Referencia: Usar endpoint `/categories` |

#### Parámetros de Cuentas (origin_account / destination_account)

| Campo | Tipo | Requerido | Descripción | Formato |
|-------|------|-----------|-------------|---------|
| `cuit` | String | ✅ | CUIT/CUIL del titular | Formato: "20123456789" (11 dígitos) |
| `cbu` | String | ❌ | CBU de la cuenta | Formato: 22 dígitos |
| `cvu` | String | ❌ | CVU de billetera virtual | Formato: 22 dígitos |
| `alias` | String | ❌ | Alias de la cuenta | Texto alfanumérico con puntos |
| `name` | String | ✅ | Nombre del titular | Texto libre |

#### Request Body Example
```json
{
  "customer_id": 123,
  "amount": 1000.50,
  "date": "2025-08-03",
  "collection_trans_type": "movimiento_recaudacion",
  "service_id": 45,
  "operation_id": 67,
  "description": "Pago de servicios",
  "currency_id": 1,
  "origin_type": "externo",
  "origin_account": {
    "cuit": "20123456789",
    "cbu": "0123456789012345678901",
    "cvu": "0000003100012345678912",
    "alias": "mi.alias.banco",
    "name": "Cuenta Origen Externa"
  },
  "destination_account": {
    "cuit": "27987654321",
    "cbu": "9876543210987654321098",
    "cvu": "0000003100098765432198",
    "alias": "destino.alias",
    "name": "Cuenta Destino"
  },
  "commission": 2.5,
  "categories": [1, 2, 3]
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "id": 456,
    "transaction_name": "TXN-2025-0001",
    "status": "aprobado",
    "commission_amount": 25.01,
    "real_balance": 5000.00,
    "available_balance": 4500.00
  },
  "message": "Transacción creada exitosamente"
}
```

### 1.2 Obtener Transacciones
**GET** `/transactions`

Recupera lista de transacciones con filtros opcionales.

#### cURL Examples
```bash
# Obtener todas las transacciones (con paginación)
curl -X GET "https://tu-instancia-odoo.com/api/collection/transactions?limit=20&offset=0" \
  -H "Authorization: Bearer your-api-key"

# Filtrar por cliente y fechas
curl -X GET "https://tu-instancia-odoo.com/api/collection/transactions?customer_id=123&date_from=2025-07-01&date_to=2025-08-03" \
  -H "Authorization: Bearer your-api-key"

# Filtrar por estado y tipo
curl -X GET "https://tu-instancia-odoo.com/api/collection/transactions?transaction_state=aprobado&collection_trans_type=movimiento_recaudacion" \
  -H "Authorization: Bearer your-api-key"
```

#### Parámetros de Query String

| Parámetro | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-----------|------|-----------|-------------|-------------------------------|
| `customer_id` | Integer | ❌ | ID del cliente | Referencia: Usar endpoint `/customers` |
| `date_from` | String | ❌ | Fecha desde | Formato: "YYYY-MM-DD" |
| `date_to` | String | ❌ | Fecha hasta | Formato: "YYYY-MM-DD" |
| `transaction_state` | String | ❌ | Estado de la transacción | `"aprobado"`, `"pendiente"`, `"rechazado"`, `"interno"` |
| `collection_trans_type` | String | ❌ | Tipo de transacción | `"movimiento_recaudacion"`, `"retiro"`, `"movimiento_interno"` |
| `service_id` | Integer | ❌ | ID del servicio | Referencia: Usar endpoint `/services` |
| `operation_id` | Integer | ❌ | ID de la operación | Referencia: Usar endpoint `/operations` |
| `limit` | Integer | ❌ | Límite de resultados | Valor numérico (default: 50, máx: 1000) |
| `offset` | Integer | ❌ | Offset para paginación | Valor numérico (default: 0) |

#### Response
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "id": 456,
        "transaction_name": "TXN-2025-0001",
        "customer": {
          "id": 123,
          "name": "Cliente Ejemplo",
          "vat": "20123456789"
        },
        "amount": 1000.50,
        "currency": {
          "id": 1,
          "name": "ARS",
          "symbol": "$"
        },
        "date": "2025-08-03",
        "collection_trans_type": "movimiento_recaudacion",
        "transaction_state": "aprobado",
        "service": {
          "id": 45,
          "name": "Servicio de Pago"
        },
        "commission": 2.5,
        "commission_amount": 25.01,
        "description": "Pago de servicios",
        "created_at": "2025-08-03T10:30:00Z"
      }
    ],
    "total_count": 150,
    "has_next": true
  }
}
```

### 1.3 Obtener Transacción por ID
**GET** `/transactions/{id}`

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/transactions/456 \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": {
    "id": 456,
    "transaction_name": "TXN-2025-0001",
    "customer": {
      "id": 123,
      "name": "Cliente Ejemplo",
      "vat": "20123456789",
      "email": "cliente@ejemplo.com"
    },
    "amount": 1000.50,
    "currency": {
      "id": 1,
      "name": "ARS",
      "symbol": "$"
    },
    "date": "2025-08-03",
    "collection_trans_type": "movimiento_recaudacion",
    "transaction_state": "aprobado",
    "service": {
      "id": 45,
      "name": "Servicio de Pago",
      "commission": 2.5,
      "commission_app_rate": 1.5
    },
    "operation": {
      "id": 67,
      "name": "Transferencia Bancaria"
    },
    "origin_account": {
      "type": "externo",
      "cuit": "20123456789",
      "cbu": "0123456789012345678901",
      "cvu": "0000003100012345678912",
      "alias": "mi.alias.banco",
      "name": "Cuenta Origen Externa"
    },
    "destination_account": {
      "cuit": "27987654321",
      "cbu": "9876543210987654321098",
      "cvu": "0000003100098765432198",
      "alias": "destino.alias",
      "name": "Cuenta Destino"
    },
    "commission": 2.5,
    "commission_amount": 25.01,
    "balances": {
      "real_balance": 5000.00,
      "available_balance": 4500.00,
      "total_balance": 5500.00
    },
    "categories": [
      {"id": 1, "name": "Servicios"},
      {"id": 2, "name": "Pagos"}
    ],
    "is_commission": false,
    "is_concilied": false,
    "description": "Pago de servicios",
    "created_at": "2025-08-03T10:30:00Z",
    "updated_at": "2025-08-03T10:30:00Z"
  }
}
```

### 1.4 Actualizar Transacción
**PUT** `/transactions/{id}`

#### cURL Example
```bash
curl -X PUT https://tu-instancia-odoo.com/api/collection/transactions/456 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "amount": 1500.75,
    "description": "Descripción actualizada",
    "transaction_state": "pendiente",
    "commission": 3.0
  }'
```

#### Parámetros de Request (Actualización Parcial)

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `amount` | Float | ❌ | Nuevo monto de la transacción | Valor numérico |
| `description` | String | ❌ | Nueva descripción | Texto libre (máx 500 caracteres) |
| `transaction_state` | String | ❌ | Nuevo estado | `"aprobado"`, `"pendiente"`, `"rechazado"`, `"interno"` |
| `commission` | Float | ❌ | Nueva comisión | Valor numérico |
| `service_id` | Integer | ❌ | Nuevo servicio | Referencia: Usar endpoint `/services` |
| `operation_id` | Integer | ❌ | Nueva operación | Referencia: Usar endpoint `/operations` |
| `categories` | Array[Integer] | ❌ | Nuevas categorías | Referencia: Usar endpoint `/categories` |

#### Request Body Example
```json
{
  "amount": 1500.75,
  "description": "Descripción actualizada",
  "transaction_state": "pendiente",
  "commission": 3.0
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "id": 456,
    "updated_fields": ["amount", "description", "transaction_state", "commission"],
    "new_commission_amount": 45.02
  },
  "message": "Transacción actualizada exitosamente"
}
```

### 1.5 Eliminar Transacción
**DELETE** `/transactions/{id}`

#### cURL Example
```bash
curl -X DELETE https://tu-instancia-odoo.com/api/collection/transactions/456 \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "message": "Transacción eliminada exitosamente"
}
```

### 1.6 Cambiar Estado de Transacción
**PATCH** `/transactions/{id}/status`

#### cURL Example
```bash
curl -X PATCH https://tu-instancia-odoo.com/api/collection/transactions/456/status \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "transaction_state": "aprobado"
  }'
```

#### Request Body
```json
{
  "transaction_state": "aprobado"
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "id": 456,
    "previous_state": "pendiente",
    "new_state": "aprobado"
  },
  "message": "Estado actualizado exitosamente"
}
```

---

## 2. Endpoints de Servicios

### 2.1 Obtener Servicios
**GET** `/services`

#### cURL Examples
```bash
# Obtener todos los servicios
curl -X GET https://tu-instancia-odoo.com/api/collection/services \
  -H "Authorization: Bearer your-api-key"

# Filtrar servicios por cliente
curl -X GET "https://tu-instancia-odoo.com/api/collection/services?customer_id=123" \
  -H "Authorization: Bearer your-api-key"

# Solo servicios activos
curl -X GET "https://tu-instancia-odoo.com/api/collection/services?active_only=true" \
  -H "Authorization: Bearer your-api-key"
```

#### Parámetros de Query String

| Parámetro | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-----------|------|-----------|-------------|-------------------------------|
| `customer_id` | Integer | ❌ | ID del cliente | Referencia: Usar endpoint `/customers` |
| `active_only` | Boolean | ❌ | Solo servicios activos | `true`, `false` (default: `true`) |
| `service_id` | Integer | ❌ | ID del servicio específico | Referencia: Usar endpoint `/operations` |

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 45,
      "customer": {
        "id": 123,
        "name": "Cliente Ejemplo"
      },
      "service": {
        "id": 78,
        "name": "Servicio de Pago",
        "type": "service"
      },
      "commission": 2.5,
      "commission_app_rate": 1.5,
      "name_account": "Cuenta Principal",
      "bank": {
        "id": 12,
        "name": "Banco Ejemplo"
      },
      "cbu": "0123456789012345678901",
      "cvu": "0000003100012345678912",
      "alias": "mi.alias.banco",
      "cuit": "20123456789",
      "agent_commissions": [
        {
          "agent_id": 34,
          "agent_name": "Agente Ejemplo",
          "commission_rate": 0.5
        }
      ]
    }
  ]
}
```

### 2.2 Crear Servicio
**POST** `/services`

#### cURL Example
```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/services \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "service_id": 78,
    "commission": 2.5,
    "commission_app_rate": 1.5,
    "name_account": "Cuenta Principal",
    "bank_id": 12,
    "cbu": "0123456789012345678901",
    "cvu": "0000003100012345678912",
    "alias": "mi.alias.banco",
    "cuit": "20123456789",
    "agent_commissions": [
      {
        "agent_id": 34,
        "commission_rate": 0.5
      }
    ]
  }'
```

#### Parámetros de Request

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `customer_id` | Integer | ✅ | ID del cliente | Referencia: Usar endpoint `/customers` |
| `service_id` | Integer | ✅ | ID del servicio/operación | Referencia: Usar endpoint `/operations` |
| `commission` | Float | ✅ | Comisión del servicio | Valor numérico (porcentaje) |
| `commission_app_rate` | Float | ❌ | Comisión de la app | Valor numérico (porcentaje) |
| `name_account` | String | ✅ | Nombre de la cuenta | Texto libre |
| `bank_id` | Integer | ❌ | ID del banco | Referencia: Usar endpoint `/banks` |
| `cbu` | String | ❌ | CBU de la cuenta | Formato: 22 dígitos |
| `cvu` | String | ❌ | CVU de billetera virtual | Formato: 22 dígitos |
| `alias` | String | ❌ | Alias de la cuenta | Texto alfanumérico con puntos |
| `cuit` | String | ✅ | CUIT/CUIL del titular | Formato: "20123456789" (11 dígitos) |

#### Parámetros de Comisiones de Agentes (agent_commissions)

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `agent_id` | Integer | ✅ | ID del agente | Referencia: Usar endpoint `/customers` (agentes) |
| `commission_rate` | Float | ✅ | Porcentaje de comisión | Valor numérico (0.0 - 100.0) |

#### Request Body Example
```json
{
  "customer_id": 123,
  "service_id": 78,
  "commission": 2.5,
  "commission_app_rate": 1.5,
  "name_account": "Cuenta Principal",
  "bank_id": 12,
  "cbu": "0123456789012345678901",
  "cvu": "0000003100012345678912",
  "alias": "mi.alias.banco",
  "cuit": "20123456789",
  "agent_commissions": [
    {
      "agent_id": 34,
      "commission_rate": 0.5
    }
  ]
}
```

---

## 3. Endpoints de Clientes

### 3.1 Obtener Clientes
**GET** `/customers`

#### cURL Examples
```bash
# Obtener todos los clientes
curl -X GET https://tu-instancia-odoo.com/api/collection/customers \
  -H "Authorization: Bearer your-api-key"

# Buscar cliente por nombre
curl -X GET "https://tu-instancia-odoo.com/api/collection/customers?name=Cliente%20Ejemplo" \
  -H "Authorization: Bearer your-api-key"

# Buscar por CUIT
curl -X GET "https://tu-instancia-odoo.com/api/collection/customers?vat=20123456789" \
  -H "Authorization: Bearer your-api-key"

# Solo clientes activos
curl -X GET "https://tu-instancia-odoo.com/api/collection/customers?active_only=true" \
  -H "Authorization: Bearer your-api-key"
```

#### Parámetros de Query String

| Parámetro | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-----------|------|-----------|-------------|-------------------------------|
| `name` | String | ❌ | Filtrar por nombre | Búsqueda parcial (case-insensitive) |
| `vat` | String | ❌ | Filtrar por CUIT/VAT | Formato: "20123456789" |
| `email` | String | ❌ | Filtrar por email | Email válido |
| `active_only` | Boolean | ❌ | Solo clientes activos | `true`, `false` (default: `true`) |
| `is_company` | Boolean | ❌ | Tipo de cliente | `true` (empresa), `false` (persona) |
| `limit` | Integer | ❌ | Límite de resultados | Valor numérico (default: 50) |
| `offset` | Integer | ❌ | Offset para paginación | Valor numérico (default: 0) |

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "name": "Cliente Ejemplo",
      "vat": "20123456789",
      "email": "cliente@ejemplo.com",
      "phone": "+5491112345678",
      "is_company": true,
      "active": true,
      "total_balance": 5500.00,
      "available_balance": 4500.00,
      "real_balance": 5000.00
    }
  ]
}
```

### 3.2 Obtener Saldos de Cliente
**GET** `/customers/{id}/balance`

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/customers/123/balance \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": {
    "customer_id": 123,
    "balances": {
      "total_balance": 5500.00,
      "available_balance": 4500.00,
      "real_balance": 5000.00
    },
    "currency_balances": {
      "ARS": 4000.00,
      "USD": 100.00,
      "EUR": 50.00,
      "BRL": 0.00
    },
    "last_updated": "2025-08-03T10:30:00Z"
  }
}
```

---

## 4. Endpoints de Operaciones

### 4.1 Obtener Operaciones
**GET** `/operations`

#### Parámetros de Query String

| Parámetro | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-----------|------|-----------|-------------|-------------------------------|
| `active_only` | Boolean | ❌ | Solo operaciones activas | `true`, `false` (default: `true`) |

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/operations \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 67,
      "name": "Transferencia Bancaria",
      "collection_type": "operation",
      "active": true
    },
    {
      "id": 68,
      "name": "Pago con Tarjeta",
      "collection_type": "operation",
      "active": true
    }
  ]
}
```

### 4.2 Crear Operación
**POST** `/operations`

#### Parámetros de Request

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `name` | String | ✅ | Nombre de la operación | Texto libre (máx 200 caracteres) |
| `active` | Boolean | ❌ | Estado activo | `true`, `false` (default: `true`) |

#### cURL Example
```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/operations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Pago con Billetera Digital",
    "active": true
  }'
```

#### Request Body Example
```json
{
  "name": "Pago con Billetera Digital",
  "active": true
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "id": 69,
    "name": "Pago con Billetera Digital"
  },
  "message": "Operación creada exitosamente"
}
```

---

## 5. Endpoints de Categorías

### 5.1 Obtener Categorías
**GET** `/categories`

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/categories \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "Servicios"
    },
    {
      "id": 2,
      "name": "Pagos"
    }
  ]
}
```

### 5.2 Crear Categoría
**POST** `/categories`

#### cURL Example
```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/categories \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Nueva Categoría"
  }'
```

#### Parámetros de Request

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `name` | String | ✅ | Nombre de la categoría | Texto libre (máx 100 caracteres) |

#### Request Body Example
```json
{
  "name": "Nueva Categoría"
}
```

---

## 6. Endpoints de Reportes

### 6.1 Generar Reporte de Transacciones
**POST** `/reports/transactions`

#### cURL Example
```bash
curl -X POST https://tu-instancia-odoo.com/api/collection/reports/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "date_from": "2025-07-01",
    "date_to": "2025-07-31",
    "format": "pdf"
  }'
```

#### Parámetros de Request

| Campo | Tipo | Requerido | Descripción | Valores Posibles / Referencias |
|-------|------|-----------|-------------|-------------------------------|
| `customer_id` | Integer | ❌ | ID del cliente | Referencia: Usar endpoint `/customers` |
| `date_from` | String | ✅ | Fecha desde | Formato: "YYYY-MM-DD" |
| `date_to` | String | ✅ | Fecha hasta | Formato: "YYYY-MM-DD" |
| `format` | String | ❌ | Formato del reporte | `"pdf"`, `"excel"`, `"csv"` (default: `"pdf"`) |
| `transaction_state` | String | ❌ | Filtrar por estado | `"aprobado"`, `"pendiente"`, `"rechazado"`, `"interno"` |
| `collection_trans_type` | String | ❌ | Filtrar por tipo | `"movimiento_recaudacion"`, `"retiro"`, `"movimiento_interno"` |
| `include_details` | Boolean | ❌ | Incluir detalles | `true`, `false` (default: `true`) |

#### Request Body Example
```json
{
  "customer_id": 123,
  "date_from": "2025-07-01",
  "date_to": "2025-07-31",
  "format": "pdf"
}
```

#### Response
```json
{
  "success": true,
  "data": {
    "report_url": "https://tu-instancia-odoo.com/reports/12345.pdf",
    "expires_at": "2025-08-04T10:30:00Z"
  }
}
```

---

## 7. Endpoints Utilitarios

### 7.1 Obtener Monedas
**GET** `/currencies`

#### Parámetros de Query String

*Este endpoint no requiere parámetros adicionales*

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/currencies \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "ARS",
      "symbol": "$",
      "full_name": "Peso Argentino",
      "active": true
    },
    {
      "id": 2,
      "name": "USD",
      "symbol": "$",
      "full_name": "Dólar Estadounidense",
      "active": true
    }
  ]
}
```

### 7.2 Obtener Bancos
**GET** `/banks`

#### Parámetros de Query String

*Este endpoint no requiere parámetros adicionales*

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/banks \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {
      "id": 12,
      "name": "Banco Galicia",
      "bic": "GALIARCABXXX",
      "active": true
    },
    {
      "id": 13,
      "name": "Banco Macro",
      "bic": "MACRAR22XXX",
      "active": true
    }
  ]
}
```

### 7.3 Obtener Tipos de Transacción
**GET** `/config/transaction-types`

#### Parámetros de Query String

*Este endpoint no requiere parámetros adicionales*

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/config/transaction-types \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {"key": "movimiento_recaudacion", "label": "Acreditación"},
    {"key": "retiro", "label": "Mov. Retiro"},
    {"key": "movimiento_interno", "label": "Mov. Interno"}
  ]
}
```

### 7.4 Obtener Estados de Transacción
**GET** `/config/transaction-states`

#### Parámetros de Query String

*Este endpoint no requiere parámetros adicionales*

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/config/transaction-states \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": [
    {"key": "aprobado", "label": "Aprobado"},
    {"key": "pendiente", "label": "Pendiente"},
    {"key": "rechazado", "label": "Rechazado"},
    {"key": "interno", "label": "Interno"}
  ]
}
```

### 7.5 Obtener Estadísticas Generales
**GET** `/statistics`

#### Parámetros de Query String

*Este endpoint no requiere parámetros adicionales*

#### cURL Example
```bash
curl -X GET https://tu-instancia-odoo.com/api/collection/statistics \
  -H "Authorization: Bearer your-api-key"
```

#### Response
```json
{
  "success": true,
  "data": {
    "total_transactions": 15847,
    "total_customers": 1250,
    "total_services": 89,
    "pending_transactions": 127,
    "approved_transactions": 14250,
    "currency_stats": {
      "ARS": {
        "count": 14500,
        "total_amount": 125000000.50
      },
      "USD": {
        "count": 1200,
        "total_amount": 850000.75
      }
    }
  }
}
```

---

## 8. Webhooks

### 7.1 Configurar Webhooks
Para recibir notificaciones en tiempo real de eventos:

#### Eventos Disponibles
- `transaction.created`: Nueva transacción creada
- `transaction.updated`: Transacción actualizada
- `transaction.state_changed`: Estado de transacción cambiado
- `balance.updated`: Saldo de cliente actualizado

#### Estructura del Webhook
```json
{
  "event": "transaction.created",
  "timestamp": "2025-08-03T10:30:00Z",
  "data": {
    "transaction_id": 456,
    "customer_id": 123,
    "amount": 1000.50,
    "transaction_state": "aprobado"
  }
}
```

---

## 9. Códigos de Error

### Códigos HTTP
- `200`: OK
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Unprocessable Entity
- `500`: Internal Server Error

### Estructura de Error
```json
{
  "success": false,
  "error": {
    "code": "INVALID_AMOUNT",
    "message": "El monto debe ser mayor a 0",
    "details": {
      "field": "amount",
      "value": -100
    }
  }
}
```

---

## 9. Límites y Paginación

### Límites de Rate
- 1000 requests por hora por API key
- 100 requests por minuto por IP

### Paginación
Usar parámetros `limit` y `offset`:
```
GET /transactions?limit=20&offset=40
```

---

## 11. Ejemplos de Uso

### Ejemplos cURL Completos

#### Autenticación
```bash
# Login para obtener tokens
curl -X POST https://tu-instancia-odoo.com/api/collection/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "tu_usuario",
    "password": "tu_contraseña"
  }'

# Validar token
curl -X GET https://tu-instancia-odoo.com/api/collection/auth/validate \
  -H "Authorization: Bearer your-api-key"

# Renovar token JWT
curl -X POST https://tu-instancia-odoo.com/api/collection/auth/refresh \
  -H "Authorization: Bearer your-jwt-token"
```

#### Gestión de Clientes
```bash
# Crear un nuevo cliente
curl -X POST https://tu-instancia-odoo.com/api/collection/customers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Empresa Nueva S.A.",
    "vat": "20987654321",
    "email": "contacto@empresanueva.com",
    "phone": "+5491198765432",
    "is_company": true
  }'

# Obtener transacciones de un cliente
curl -X GET "https://tu-instancia-odoo.com/api/collection/customers/123/transactions?limit=10&date_from=2025-07-01" \
  -H "Authorization: Bearer your-api-key"

# Actualizar datos de cliente
curl -X PUT https://tu-instancia-odoo.com/api/collection/customers/123 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "email": "nuevo-email@empresa.com",
    "phone": "+5491199887766"
  }'
```

#### Gestión de Servicios
```bash
# Obtener servicio específico
curl -X GET https://tu-instancia-odoo.com/api/collection/services/45 \
  -H "Authorization: Bearer your-api-key"

# Actualizar servicio
curl -X PUT https://tu-instancia-odoo.com/api/collection/services/45 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "commission": 3.0,
    "commission_app_rate": 1.8,
    "name_account": "Cuenta Actualizada"
  }'

# Eliminar servicio
curl -X DELETE https://tu-instancia-odoo.com/api/collection/services/45 \
  -H "Authorization: Bearer your-api-key"
```

#### Transacciones Avanzadas
```bash
# Crear transacción de retiro
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "amount": -500.00,
    "date": "2025-08-03",
    "collection_trans_type": "retiro",
    "service_id": 45,
    "description": "Retiro de fondos",
    "destination_account": {
      "cuit": "20123456789",
      "cbu": "0123456789012345678901",
      "alias": "cuenta.retiro",
      "name": "Cuenta para Retiro"
    }
  }'

# Crear movimiento interno
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "amount": 750.00,
    "date": "2025-08-03",
    "collection_trans_type": "movimiento_interno",
    "customer_destination": 456,
    "description": "Transferencia entre cuentas internas"
  }'
```

#### Reportes y Analytics
```bash
# Obtener resumen de saldos
curl -X GET https://tu-instancia-odoo.com/api/collection/reports/balance-summary \
  -H "Authorization: Bearer your-api-key"

# Analytics con filtros de fecha
curl -X GET "https://tu-instancia-odoo.com/api/collection/reports/transaction-analytics?date_from=2025-07-01&date_to=2025-08-03&customer_id=123" \
  -H "Authorization: Bearer your-api-key"

# Resumen de comisiones
curl -X GET "https://tu-instancia-odoo.com/api/collection/reports/commission-summary?date_from=2025-07-01&date_to=2025-07-31" \
  -H "Authorization: Bearer your-api-key"
```

#### Utilidades y Configuración
```bash
# Obtener todas las monedas
curl -X GET https://tu-instancia-odoo.com/api/collection/currencies \
  -H "Authorization: Bearer your-api-key"

# Obtener bancos
curl -X GET https://tu-instancia-odoo.com/api/collection/banks \
  -H "Authorization: Bearer your-api-key"

# Obtener tipos de transacción disponibles
curl -X GET https://tu-instancia-odoo.com/api/collection/config/transaction-types \
  -H "Authorization: Bearer your-api-key"

# Obtener estados de transacción
curl -X GET https://tu-instancia-odoo.com/api/collection/config/transaction-states \
  -H "Authorization: Bearer your-api-key"

# Obtener estadísticas generales
curl -X GET https://tu-instancia-odoo.com/api/collection/statistics \
  -H "Authorization: Bearer your-api-key"
```

#### Gestión de Operaciones y Categorías
```bash
# Crear nueva operación
curl -X POST https://tu-instancia-odoo.com/api/collection/operations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Pago con Billetera Digital",
    "active": true
  }'

# Actualizar categoría
curl -X PUT https://tu-instancia-odoo.com/api/collection/categories/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "name": "Servicios Actualizados"
  }'

# Eliminar categoría
curl -X DELETE https://tu-instancia-odoo.com/api/collection/categories/1 \
  -H "Authorization: Bearer your-api-key"
```

### Ejemplos de Testing con cURL

#### Test de Conectividad
```bash
# Verificar que la API está funcionando
curl -X GET https://tu-instancia-odoo.com/api/collection/statistics \
  -H "Authorization: Bearer your-api-key" \
  -w "\nHTTP Status: %{http_code}\nTime: %{time_total}s\n"
```

#### Test de Autenticación
```bash
# Test con API key válida
curl -X GET https://tu-instancia-odoo.com/api/collection/auth/validate \
  -H "Authorization: Bearer valid-api-key" \
  -w "\nStatus: %{http_code}\n"

# Test con API key inválida (debería retornar 401)
curl -X GET https://tu-instancia-odoo.com/api/collection/auth/validate \
  -H "Authorization: Bearer invalid-api-key" \
  -w "\nStatus: %{http_code}\n"
```

#### Test de Validaciones
```bash
# Test de validación - crear transacción sin campos requeridos
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{}' \
  -w "\nStatus: %{http_code}\n"

# Test de validación - monto negativo en acreditación
curl -X POST https://tu-instancia-odoo.com/api/collection/transactions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "customer_id": 123,
    "amount": -100.00,
    "collection_trans_type": "movimiento_recaudacion"
  }' \
  -w "\nStatus: %{http_code}\n"
```

### Script de Testing Completo
```bash
#!/bin/bash

# Configuración
BASE_URL="https://tu-instancia-odoo.com/api/collection"
API_KEY="your-api-key"

echo "=== Testing Collection Transaction API ==="

# Test 1: Verificar conectividad
echo "1. Testing connectivity..."
response=$(curl -s -w "%{http_code}" -X GET "${BASE_URL}/statistics" \
  -H "Authorization: Bearer ${API_KEY}")
status=${response: -3}
if [ $status -eq 200 ]; then
  echo "✅ API is accessible"
else
  echo "❌ API not accessible (Status: $status)"
  exit 1
fi

# Test 2: Crear transacción
echo "2. Creating transaction..."
create_response=$(curl -s -X POST "${BASE_URL}/transactions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_KEY}" \
  -d '{
    "customer_id": 123,
    "amount": 100.00,
    "collection_trans_type": "movimiento_recaudacion",
    "description": "Test transaction"
  }')

transaction_id=$(echo $create_response | grep -o '"id":[0-9]*' | cut -d':' -f2)
if [ ! -z "$transaction_id" ]; then
  echo "✅ Transaction created with ID: $transaction_id"
else
  echo "❌ Failed to create transaction"
  echo "$create_response"
fi

# Test 3: Obtener transacción
echo "3. Getting transaction..."
if [ ! -z "$transaction_id" ]; then
  get_response=$(curl -s -w "%{http_code}" -X GET "${BASE_URL}/transactions/${transaction_id}" \
    -H "Authorization: Bearer ${API_KEY}")
  get_status=${get_response: -3}
  if [ $get_status -eq 200 ]; then
    echo "✅ Transaction retrieved successfully"
  else
    echo "❌ Failed to retrieve transaction (Status: $get_status)"
  fi
fi

# Test 4: Obtener saldo de cliente
echo "4. Getting customer balance..."
balance_response=$(curl -s -w "%{http_code}" -X GET "${BASE_URL}/customers/123/balance" \
  -H "Authorization: Bearer ${API_KEY}")
balance_status=${balance_response: -3}
if [ $balance_status -eq 200 ]; then
  echo "✅ Customer balance retrieved"
else
  echo "❌ Failed to get customer balance (Status: $balance_status)"
fi

echo "=== Testing completed ==="
```

### Ejemplo: Crear transacción completa
```python
import requests

url = "https://tu-instancia-odoo.com/api/collection/transactions"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-api-key"
}

data = {
    "customer_id": 123,
    "amount": 1000.50,
    "date": "2025-08-03",
    "collection_trans_type": "movimiento_recaudacion",
    "service_id": 45,
    "operation_id": 67,
    "description": "Pago de servicios",
    "currency_id": 1,
    "origin_type": "externo",
    "origin_account": {
        "cuit": "20123456789",
        "cbu": "0123456789012345678901",
        "alias": "mi.alias.banco",
        "name": "Cuenta Origen Externa"
    }
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

### Ejemplo: Consultar saldo de cliente
```javascript
const axios = require('axios');

const config = {
  headers: {
    'Authorization': 'Bearer your-api-key',
    'Content-Type': 'application/json'
  }
};

axios.get('https://tu-instancia-odoo.com/api/collection/customers/123/balance', config)
  .then(response => {
    console.log(response.data);
  })
  .catch(error => {
    console.error(error.response.data);
  });
```

---

## 12. Validaciones

### Campos Requeridos para Crear Transacción
- `customer_id`: ID del cliente válido
- `amount`: Monto mayor a 0
- `collection_trans_type`: Tipo válido de transacción
- `service_id`: ID de servicio válido (para algunos tipos)

### Validaciones de Negocio
- No se pueden eliminar comisiones directamente
- Los montos negativos solo se permiten para retiros
- Las transacciones conciliadas no se pueden modificar

---

## 13. Resumen de Endpoints y Parámetros

### Tabla Resumen de Endpoints

| Endpoint | Método | Parámetros Principales | Referencias Requeridas |
|----------|---------|----------------------|----------------------|
| `/transactions` | POST | `customer_id`, `amount`, `collection_trans_type` | `/customers`, `/services`, `/operations` |
| `/transactions` | GET | `customer_id`, `date_from`, `date_to` | `/customers` |
| `/transactions/{id}` | PUT | `amount`, `transaction_state` | - |
| `/services` | GET | `customer_id`, `active_only` | `/customers` |
| `/services` | POST | `customer_id`, `service_id`, `commission` | `/customers`, `/operations`, `/banks` |
| `/customers` | GET | `name`, `vat`, `active_only` | - |
| `/customers/{id}/balance` | GET | - | - |
| `/operations` | GET | `active_only` | - |
| `/operations` | POST | `name`, `active` | - |
| `/categories` | GET | - | - |
| `/categories` | POST | `name` | - |
| `/categories/{id}` | PUT | `name` | - |
| `/reports/transactions` | POST | `date_from`, `date_to`, `format` | `/customers` |
| `/currencies` | GET | - | - |
| `/banks` | GET | - | - |
| `/config/transaction-types` | GET | - | - |
| `/config/transaction-states` | GET | - | - |
| `/statistics` | GET | - | - |

### Campos de Referencia Críticos

> ⚠️ **Importante**: Antes de usar estos IDs en requests, asegúrate de obtenerlos desde los endpoints de referencia correspondientes.

| Campo | Endpoint de Referencia | Modelo de Odoo | Descripción |
|-------|----------------------|----------------|-------------|
| `customer_id` | `GET /customers` | `res.partner` | Cliente o agente del sistema |
| `service_id` | `GET /operations` | `product.template` | Servicio/operación disponible |
| `operation_id` | `GET /operations` | `product.template` | Operación específica |
| `currency_id` | `GET /currencies` | `res.currency` | Moneda del sistema |
| `bank_id` | `GET /banks` | `res.bank` | Banco registrado |
| `categories` | `GET /categories` | `collection.category` | Categorías de transacciones |

---

Este documento proporciona una guía completa para integrar con el módulo de transacciones comerciales. Para más información o soporte técnico, contactar al equipo de desarrollo.
