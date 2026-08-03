# Portal Club Support — JogaJunto

Módulo Odoo 18 que implementa en el portal una experiencia de registro de usuario y selección de clubes de apoyo para plataformas de juegos y apuestas.

**Diseño:** split-screen con panel de branding izquierdo (verde oscuro) + panel de formulario derecho (blanco). Tres pasos: Seus dados → Seus clubes → Pronto.

## Instalación

1. Copiar la carpeta `portal_club_support` en el directorio `addons` de Odoo.
2. Actualizar la lista de módulos: Ajustes → Aplicaciones → Actualizar lista.
3. Buscar "Portal Club Support" e instalar.
4. Los datos demo (3 categorías + 12 clubes brasileños) se cargan automáticamente.

## Flujo del Usuario

```
Login → "Não tem uma conta?" → /club-support/register (público)
  → Step 1: Completa dados pessoais → crea cuenta → auto-login
  → Step 2: /my/club-support/clubs → elige clubes por categoría
  → Step 3: Confirmación "Pronto"
  → Dashboard: /my/club-support
```

## Configuración

### Categorías de Juego
Menú **JogaJunto → Configuración → Categorías de Juego**

- Crear/editar categorías con nombre, código único, ícono, color, descripción de comisión.
- Asignar clubes disponibles para cada categoría.
- Marcar como "obligatoria" si el usuario debe elegir un club.
- Los campos `icon` y `color` definen la apariencia en el portal.

### Clubes
Menú **JogaJunto → Configuración → Clubes**

- Registrar clubes con nombre, abreviatura, escudo, colores y porcentaje de comisión.
- Asignar clubes a categorías desde la vista de categoría o desde el club.
- `primary_color` se usa para el badge circular del club en el portal.

### Preferencias de Usuarios
Menú **JogaJunto → Preferencias de Usuarios**

- Vista de todas las preferencias registradas.
- Filtros por usuario, categoría, club, fecha y estado (vigente/histórico).

## Rutas del Portal

| Ruta | Auth | Descripción |
|------|------|------------|
| `/club-support/register` | público | Step 1: formulario de datos + creación de cuenta |
| `/my/club-support/clubs` | user | Step 2: selección de clubes por categoría |
| `/my/club-support/save` | user | POST: guarda preferencias |
| `/my/club-support` | user | Dashboard con resumen + datos personales |

Desde `/my` también aparece la entrada "Clubes Apoiados" con contador de preferencias activas.

El link "Não tem uma conta?" en el login (`/web/login`) apunta a `/club-support/register`.

## Diseño

- **Split-screen**: panel branding verde oscuro (42%) + formulario blanco (58%)
- **Tipografía**: sans-serif moderna, tamaños escalonados
- **Colores**: verde oscuro `#0a2e1f`, lima `#32d74b`, blanco, grises neutros
- **Variables SCSS**: todos los colores y radios modificables desde `:root`
- **3-step indicator**: círculos numerados con conectores y estado done/active
- **Toast notifications**: confirmación animada abajo-derecha
- **Responsive**: mobile-first con breakpoints en 768px y 480px
- **Sin frameworks externos**: CSS vanilla + JS nativo

## Pruebas Manuales

1. **Instalación**: verificar que el módulo instala sin errores y los datos demo se cargan (3 categorías, 12 clubes).
2. **Backend**: navegar por los menús de JogaJunto, crear/editar categorías y clubes.
3. **Login → Registro**: desde `/web/login`, click en "Não tem uma conta?" → debe ir a `/club-support/register`.
4. **Registro público**: completar Step 1 (nombre, CPF, email, fecha, contraseña) → continuar → debe crear usuario y redirigir a Step 2.
5. **Validaciones server-side**: probar sin nombre, email inválido, contraseña < 6 chars, sin checkbox de edad → debe mostrar errores.
6. **Email duplicado**: intentar registrar un email ya existente → debe mostrar mensaje.
7. **Step 2 — selección**: elegir un club en cada categoría → el tile debe mostrar borde verde y checkmark.
8. **Categoría obligatoria**: intentar enviar sin seleccionar club en categoría marcada como obligatoria → debe mostrar toast de error.
9. **Step 3 — confirmación**: después de guardar → debe mostrar resumen "Pronto" con lista de clubes elegidos.
10. **Dashboard**: ir a `/my/club-support` → debe mostrar impacto banner, clubes en grid horizontal, datos personales.
11. **Modificar clubes**: desde dashboard, "Editar escolhas" → cambiar un club → verificar que se actualiza (no duplica).
12. **Club desactivado**: desactivar un club desde backend → no debe aparecer en Step 2.
13. **Categoría archivada**: archivar una categoría → no debe aparecer en el portal.
14. **Responsive**: verificar split-screen colapsa a stacked en ≤ 768px.
15. **Sin JavaScript**: deshabilitar JS → el formulario sigue siendo enviable vía POST clásico (radios nativos).
16. **Toast**: al guardar con éxito, el dashboard debe mostrar toast verde animado.
17. **Entrada en /my**: verificar que "Clubes Apoiados" aparece con el contador de preferencias.

## Dependencias

- `portal`
- `website`
- `contacts`

Si se instala `l10n_br` (localización brasileña), el campo `l10n_br_cpf` de este módulo puede ocultarse manualmente para evitar duplicación.

## Estructura del Módulo

```
portal_club_support/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── portal.py
├── models/
│   ├── __init__.py
│   ├── game_category.py
│   ├── club.py
│   ├── preference.py
│   └── res_partner.py
├── security/
│   ├── ir.model.access.csv
│   └── security.xml
├── views/
│   ├── portal_templates.xml
│   ├── game_category_views.xml
│   ├── club_views.xml
│   ├── preference_views.xml
│   ├── res_partner_views.xml
│   └── menu_views.xml
├── data/
│   └── demo_data.xml
├── static/src/
│   ├── js/portal_club_support.js
│   └── scss/portal_club_support.scss
└── README.md
```

## Versión objetivo

Odoo 18.0 (compatible con 18 Enterprise y Community).