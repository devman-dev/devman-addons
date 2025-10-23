# Configuración Contable del Casino

## Configuración por Compañía

El módulo `casino_online_back` ahora incluye configuración contable específica para cada compañía, permitiendo definir diarios y cuentas bancarias para diferentes tipos de transacciones del casino.

### Acceso a la Configuración

1. Ir a **Configuración > Compañías > Compañías**
2. Seleccionar tu compañía
3. Ir a la pestaña **Casino**

### Campos de Configuración

#### Diarios Bancarios

- **Diario para Depósitos de Usuarios** (`casino_deposit_journal_id`)
  - Diario contable donde se registrarán los depósitos de los usuarios del casino
  - Debe ser de tipo 'Banco' o 'Efectivo'

- **Diario para Transferencias de Apuestas** (`casino_bet_transfer_journal_id`)
  - Diario contable donde se registrarán las transferencias de las apuestas y pérdidas de los usuarios
  - Debe ser de tipo 'Banco' o 'Efectivo'

#### Cuentas Contables (Opcional)

- **Cuenta para Depósitos de Usuarios** (`casino_deposit_account_id`)
  - Cuenta contable específica para registrar los depósitos de usuarios
  - Si no se especifica, se usará la cuenta por defecto del diario

- **Cuenta para Apuestas y Pérdidas** (`casino_bet_account_id`)
  - Cuenta contable específica para registrar las apuestas y pérdidas de usuarios
  - Si no se especifica, se usará la cuenta por defecto del diario

## Uso Programático

### Métodos Disponibles en `casino.game.session`

#### Obtener Configuración

```python
# Obtener diarios configurados
deposit_journal = session._get_deposit_journal()
bet_journal = session._get_bet_transfer_journal()

# Obtener cuentas configuradas
deposit_account = session._get_deposit_account()
bet_account = session._get_bet_account()
```

#### Crear Asientos Contables

```python
# Crear asiento para depósito de usuario
session.create_deposit_move(amount=100.0, description="Depósito inicial")

# Crear asiento para transferencia de apuesta
session.create_bet_transfer_move(amount=50.0, description="Apuesta perdida")
```

### Estructura de Asientos Contables

#### Depósito de Usuario
```
Diario: Configurado en casino_deposit_journal_id
Debe                           Haber
---------                      ---------
Cuenta Depósitos  100.00       
                               Cliente (Por cobrar)  100.00
```

#### Transferencia de Apuesta/Pérdida
```
Diario: Configurado en casino_bet_transfer_journal_id
Debe                           Haber
---------                      ---------
Cliente (Por cobrar)  50.00    
                               Cuenta Apuestas  50.00
```

## Validaciones

- Los diarios deben ser de tipo 'Banco' o 'Efectivo'
- Las cuentas de depósito deben ser de tipo 'Efectivo' o 'Banco'
- Las cuentas de apuestas pueden ser de tipo 'Efectivo', 'Banco' o 'Pasivo Corriente'
- Si no se configura una cuenta específica, se usará la cuenta por defecto del diario correspondiente

## Notas Importantes

1. **Configuración Obligatoria**: Los diarios deben estar configurados antes de poder crear asientos contables automáticamente.

2. **Multicompañía**: Cada compañía puede tener su propia configuración de diarios y cuentas.

3. **Flexibilidad**: El sistema permite usar las cuentas por defecto de los diarios o especificar cuentas particulares para mayor control contable.

4. **Integración**: Los asientos creados se vinculan automáticamente con la sesión de juego correspondiente a través del campo `game_session_id`.

## Ejemplo de Configuración

1. **Crear Diarios**:
   - Diario "Depósitos Casino" (tipo: Banco)
   - Diario "Apuestas Casino" (tipo: Banco)

2. **Configurar en Compañía**:
   - Asignar los diarios creados en los campos correspondientes
   - Opcionalmente, especificar cuentas contables particulares

3. **Uso en Código**:
   ```python
   # En un controlador o método de sesión
   session = self.env['casino.game.session'].browse(session_id)
   
   # Registrar depósito
   deposit_move = session.create_deposit_move(100.0, "Depósito PayPal")
   
   # Registrar apuesta perdida
   bet_move = session.create_bet_transfer_move(25.0, "Apuesta - Ruleta")
   ```