# Project Portal Dashboard

Módulo de Odoo 19 para mostrar proyectos en el portal web con KPIs.

## Características

### 1. Dashboard Principal (`/my/projects`)
- **KPIs Visuales**: Muestra tarjetas con métricas clave
  - Total de proyectos
  - Proyectos por estado
  - Porcentajes de distribución
- **Gráfico de Barras**: Visualización de la distribución de proyectos por estado
- **Lista de Proyectos**: Tabla con todos los proyectos disponibles
- **Búsqueda y Filtros**: Permite buscar y filtrar proyectos por estado
- **Ordenamiento**: Ordena por fecha, nombre o estado
- **Paginación**: Navegación eficiente para muchos proyectos

### 2. Vista Detallada de Proyecto (`/my/project/<id>`)
- **Información del Proyecto**: Nombre, cliente, estado, fechas, descripción
- **KPIs del Proyecto**:
  - Total de tareas
  - Tareas completadas
  - Tareas en progreso
- **Lista de Tareas**: Tabla con todas las tareas del proyecto
  - Nombre de la tarea
  - Asignados
  - Estado
  - Prioridad
  - Fecha límite

## Instalación

1. Copia el módulo en la carpeta `custom_addons`
2. Reinicia el servidor Odoo
3. Actualiza la lista de módulos
4. Instala el módulo "Project Portal Dashboard"

```bash
docker restart odoo
```

## Uso

1. Accede al portal de Odoo con tu usuario
2. En el menú del portal verás una nueva entrada "Proyectos"
3. Haz clic para ver el dashboard con KPIs y lista de proyectos
4. Haz clic en "Ver Detalle" de cualquier proyecto para ver más información

## Dependencias

- `project`: Módulo base de proyectos de Odoo
- `portal`: Módulo del portal de Odoo
- `website`: Módulo del sitio web de Odoo

## Personalización

### Modificar KPIs
Edita el método `portal_my_projects` en `controllers/portal.py`

### Cambiar Estilos
Modifica `static/src/css/portal_dashboard.css`

### Agregar Funcionalidades
Extiende las plantillas en `views/portal_templates.xml`

## Compatibilidad

- Odoo 19.0 Community Edition

## Licencia

LGPL-3
