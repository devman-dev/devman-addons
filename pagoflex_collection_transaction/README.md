# PagoFlex - Collection Transaction on Payment Sent (Odoo 17)

Este módulo abre un **wizard de `collection.transaction`** cuando un **`account.payment`** se marca como **enviado** (vía botón propio).

## Cambios clave para Odoo 17
- `version` del manifest: **17.0**.
- Botón propio **"Marcar como enviado + Collection"** (Odoo 17 no tiene `action_mark_as_sent` nativo para pagos).
- Validación: sólo disponible cuando el pago está **Publicado** (`state == 'posted'`).
- Evitamos depender de `is_move_sent` (no estándar en payment).

## Instalación
1. Copiar la carpeta `pagoflex_collection_transaction/` al directorio de addons.
2. Actualizar Apps y buscar **"PagoFlex - Collection Transaction on Payment Sent"**.
3. Instalar.

## Uso
- Abrí un `account.payment` **Publicado** y presioná **"Marcar como enviado + Collection"**.
- Se abrirá el formulario de `collection.transaction` con los campos precargados.

## Ajustes opcionales
- Si tu diario tiene un vínculo al banco (por ej. `journal.pagoflex_bank_id`), se prellenará `account_bank` y nombre del banco destino.
- Si tus campos de **cheque** están en otro modelo/relación, actualizá el mapeo en `_pagoflex_prepare_collection_ctx`.

Generado: 2025-08-25T00:34:43.963344