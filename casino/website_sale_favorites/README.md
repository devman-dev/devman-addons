
# Website Sale Favorites (Odoo 18)

Permite a los usuarios del Website (autenticados) marcar productos como favoritos con un botón de corazón en:
- la tarjeta de producto del grid de la tienda
- la página del producto

Los favoritos del usuario viven en `/my/favorites`.

## Instalación
1. Copiar la carpeta `website_sale_favorites` en tu `addons_path`.
2. Actualizar Apps y **instalar** el módulo.
3. Asegúrate de que los usuarios usen cuentas del Website (Portal). Los anónimos verán el botón pero al pulsar se les pedirá login.

## Notas técnicas
- Modelo `casino.game.favorite (user_id, product_tmpl_id)` con restricción única por usuario+producto.
- Controladores:
  - `POST /shop/favorite/toggle` (json) alterna estado para el usuario actual.
  - `GET /my/favorites` página con el grid reutilizando `website_sale.products_item`.
- JS: inicializa el estado en batch y alterna con `ajax.jsonRpc`.
- Seguridad: acceso para `base.group_user` (el controller usa `auth="user"`).

## Personalización
- Cambiar los íconos CSS (`.wsf-heart` / `.wsf-heart-o`) o reemplazar por SVGs propios.
- Para soportar favoritos por *variant*, cambia `product_tmpl_id` por `product_id` en el modelo y en los `t-att-data-product-id`.
