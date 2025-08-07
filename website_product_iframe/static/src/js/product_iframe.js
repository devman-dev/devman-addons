/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';

publicWidget.registry.ProductIframe = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    events: {
        'click .show-iframe': '_onShowIframe',
    },

    _onShowIframe: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const productId = $btn.data('product-id');
        const productName = encodeURIComponent($btn.data('product-name'));
        const productPrice = $btn.data('product-price');

        // URL fija como solicitaste
        const iframeUrl = 'https://kidmons.com/es/juego/matematicas-para-niños/';

        // Buscar el contenedor padre del botón
        const $container = $btn.parent();

        // Alternar iframe en el mismo espacio
        if ($container.find('iframe').length > 0) {
            // Si ya existe iframe, mostrarlo y ocultar botón
            $container.find('iframe').remove();
            $btn.show().text('🎯 Jugar Matemáticas');
        } else {
            // Crear iframe y ocultar botón
            const $iframe = $(`
                <iframe src="${iframeUrl}" 
                        width="100%" 
                        height="500px" 
                        style="border:1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                </iframe>
            `);
            
            // Agregar botón de cerrar encima del iframe
            const $closeBtn = $(`
                <button class="btn btn-sm btn-outline-secondary mb-2 close-iframe" 
                        style="float: right;">
                    ❌ Cerrar Juego
                </button>
            `);

            $btn.hide();
            $container.append($closeBtn).append($iframe);
        }
    },

    // Evento para cerrar iframe
    events: {
        'click .show-iframe': '_onShowIframe',
        'click .close-iframe': '_onCloseIframe',
    },

    _onCloseIframe: function (ev) {
        ev.preventDefault();
        const $closeBtn = $(ev.currentTarget);
        const $container = $closeBtn.parent();
        
        // Remover iframe y botón de cerrar
        $container.find('iframe, .close-iframe').remove();
        
        // Mostrar botón original
        $container.find('.show-iframe').show();
    },
});

export default publicWidget.registry.ProductIframe;