# Project Goals Portal Dashboard

Módulo de Odoo 19 para mostrar objetivos de proyectos en el portal web con KPIs de cumplimiento.

## Características

### 1. Dashboard Principal (`/goals`)
- **KPIs Visuales**: Muestra tarjetas con métricas clave
  - Total de objetivos
  - Objetivos alcanzados
  - Objetivos en progreso
  - Objetivos pendientes
  - Porcentajes de distribución
- **Gráfico de Progreso**: Visualización del progreso general con barra de progreso apilada
- **Lista de Objetivos**: Tabla con todos los objetivos disponibles
  - Nombre del objetivo
  - Proyecto asociado
  - Estado (Alcanzado/En Progreso)
  - Fecha límite
  - Barra de progreso individual
- **Búsqueda y Filtros**: Permite buscar y filtrar objetivos por estado
- **Ordenamiento**: Ordena por fecha límite, nombre o proyecto
- **Paginación**: Navegación eficiente para muchos objetivos

### 2. Vista Detallada de Objetivo (`/goal/<id>`)
- **Información del Objetivo**: Nombre, proyecto, estado, fecha límite, descripción
- **Barra de Progreso**: Visualización del progreso del objetivo
- **KPIs del Objetivo**:
  - Total de tareas asociadas
  - Tareas completadas
  - Tareas en progreso
- **Lista de Tareas**: Tabla con todas las tareas asociadas al objetivo
  - Nombre de la tarea
  - Proyecto
  - Asignados
  - Estado
  - Prioridad
  - Fecha límite

### 3. Acceso Público
- Visible para visitantes sin necesidad de login
- Entrada en el menú del sitio web
- Entrada en el portal para usuarios logueados

## Instalación

1. Copia el módulo en la carpeta `custom_addons`
2. Reinicia el servidor Odoo
3. Actualiza la lista de módulos
4. Instala el módulo "Project Goals Portal Dashboard"

```bash
docker restart odoo
```

## Uso

### Para visitantes públicos:
1. Accede a `/goals` en el sitio web
2. Navega por el dashboard con KPIs y lista de objetivos
3. Haz clic en "Ver Detalle" para ver información completa de cada objetivo

### Para usuarios del portal:
1. Accede al portal de Odoo con tu usuario
2. En el menú del portal verás una nueva entrada "Objetivos"
3. Accede para ver el dashboard completo

## Dependencias

- `project`: Módulo base de proyectos de Odoo
- `portal`: Módulo del portal de Odoo
- `website`: Módulo del sitio web de Odoo

## Rutas disponibles

- `/goals` - Dashboard principal (público)
- `/my/goals` - Dashboard en el portal (requiere login)
- `/goal/<id>` - Detalle de objetivo (público)
- `/my/goal/<id>` - Detalle de objetivo en el portal (requiere login)

## Personalización

### Modificar KPIs
Edita el método `portal_my_goals` en `controllers/portal.py`

### Cambiar Estilos
Modifica `static/src/css/portal_goals_dashboard.css`

### Agregar Funcionalidades
Extiende las plantillas en `views/portal_templates.xml`

## Compatibilidad

- Odoo 19.0 Community Edition
- Compatible con el módulo `project_portal_dashboard`

## Licencia

LGPL-3
