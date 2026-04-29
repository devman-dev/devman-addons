# Centro de Control PagoFlex

## Propuesta funcional para cliente

### Objetivo

Construir una pantalla ejecutiva y operativa dentro de Odoo que concentre, en un solo lugar, la informacion critica del gateway PagoFlex:

- continuidad de sincronizacion
- actividad transaccional
- calidad de datos y excepciones
- seguimiento de comisiones

La propuesta esta orientada a reducir tiempos de control manual, mejorar la trazabilidad operativa y ofrecer una vista profesional para la gestion diaria.

### Nombre sugerido

Centro de Control PagoFlex

### Usuarios objetivo

- Operador: monitoreo diario, deteccion de incidencias y seguimiento de transferencias
- Auditor: control de consistencia, trazabilidad y supervision de la operacion
- Administrador: vision general, rentabilidad, reglas de negocio y salud del sistema

### Alcance del dashboard

#### 1. Resumen ejecutivo

Indicadores principales del periodo seleccionado:

- transferencias del dia
- importe operado del dia
- trabajos de sincronizacion fallidos
- empresas activas
- usuarios sincronizados
- tasa de exito de sincronizacion
- comision estimada del periodo
- excepciones abiertas

#### 2. Control operativo

Panel de monitoreo para recursos sincronizados:

- usuarios
- empresas
- membresias
- cuentas bancarias
- limites de saldo negativo
- transferencias

Para cada recurso se muestra:

- ultimo estado de sincronizacion
- ultima ejecucion
- modalidad de sincronizacion
- observaciones del ultimo proceso

#### 3. Actividad del negocio

Resumen de la operacion del periodo:

- cantidad de transferencias
- distribucion por estado
- volumen monetario total
- ticket promedio
- empresas con mayor actividad
- comisionistas con mayor importe estimado

#### 4. Gestion de excepciones

El dashboard identifica desvíos o datos incompletos que requieren accion:

- usuarios sin contacto Odoo vinculado
- empresas sin partner asociado
- membresias activas sin empresa resuelta
- transferencias con vinculacion incompleta
- usuarios sin verificacion KYC

#### 5. Vision financiera

Bloque orientado al seguimiento economico:

- base operada del periodo
- comision estimada a pagar
- ranking de comisionistas
- volumen operado por empresa

### Beneficios esperados

- menor dependencia de revision manual en multiples menus
- deteccion temprana de fallas de sincronizacion
- mejor trazabilidad para auditoria
- mayor visibilidad para toma de decisiones operativas
- presentacion mas profesional del modulo frente a usuarios finales y responsables de negocio

### Enfoque visual sugerido

- cabecera con KPIs de alto impacto
- tarjetas de accion rapida para profundizar en la informacion
- secciones separadas para operacion, control y finanzas
- lenguaje visual sobrio y corporativo
- navegacion directa desde cada indicador hacia las vistas de detalle

### Implementacion propuesta

La implementacion se realiza directamente dentro del modulo pagoflex_wallet_gateway y contempla:

- nueva pantalla principal de dashboard
- nuevo menu de acceso en Operaciones
- filtros por rango de fechas
- KPIs y resumenes calculados en tiempo real desde los datos sincronizados
- accesos rapidos a transferencias, jobs, logs y excepciones

### Resultado esperado

Una primera version profesional, lista para demostracion y uso interno, que sirva como base para futuras iteraciones con graficos avanzados, exportaciones y alertas automatizadas.
