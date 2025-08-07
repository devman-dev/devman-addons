/** @odoo-module **/

import publicWidget from '@web/legacy/js/public/public_widget';
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.ProductIframe = publicWidget.Widget.extend({
    selector: '.oe_website_sale',
    events: {
        'click .show-iframe': '_onShowIframe',
        'click .show-iframe-direct': '_onShowIframeDirect',
        'click .close-iframe': '_onCloseIframe',
    },

    _onShowIframe: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const productId = $btn.data('product-id');
        const productName = encodeURIComponent($btn.data('product-name'));
        const productPrice = $btn.data('product-price');
        
        // Obtener URL del campo iframe_url del producto
        const iframeUrl = $btn.data('product-url');
        
        // Validar que existe URL
        if (!iframeUrl) {
            alert('Este juego no tiene una URL configurada.');
            return;
        }

        // Buscar el contenedor padre del botón
        const $container = $btn.parent();

        // Alternar iframe en el mismo espacio
        if ($container.find('iframe').length > 0) {
            this._closeGame($container, $btn);
        } else {
            this._startGame(productId, iframeUrl, $container, $btn);
        }
    },

    _onShowIframeDirect: function (ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget);
        const productId = $btn.data('product-id');
        const productName = encodeURIComponent($btn.data('product-name'));
        const productPrice = $btn.data('product-price');
        
        // Obtener URL del campo iframe_url del producto
        const iframeUrl = $btn.data('product-url');
        
        // Validar que existe URL
        if (!iframeUrl) {
            alert('Este juego no tiene una URL configurada.');
            return;
        }

        // Buscar el contenedor padre del botón
        const $container = $btn.parent();

        // Alternar iframe en el mismo espacio
        if ($container.find('iframe').length > 0) {
            this._closeGameDirect($container, $btn);
        } else {
            this._startGameDirect(iframeUrl, $container, $btn);
        }
    },

    _startGame: function(productId, iframeUrl, $container, $btn) {
        // Mostrar loading
        $btn.text('🔄 Iniciando...');
        $btn.prop('disabled', true);

        // Llamar al controlador para registrar movimientos
        rpc('/casino/start_game', {
            product_id: productId
        }).then((result) => {
            if (result.error) {
                alert('Error: ' + result.error);
                $btn.text('🎯 Jugar (Con Registro)');
                $btn.prop('disabled', false);
                return;
            }

            // Guardar session_id para cerrar después
            $btn.data('session-id', result.session_id);

            // Crear iframe con la URL del resultado
            const $iframe = $(`
                <iframe src="${result.iframe_url}" 
                        width="100%" 
                        height="500px" 
                        frameborder="0"
                        allowfullscreen
                        style="border:1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                </iframe>
            `);
            
            // Agregar botón de cerrar encima del iframe
            const $closeBtn = $(`
                <button class="btn btn-sm btn-outline-secondary mb-2 close-iframe" 
                        style="float: right;"
                        data-session-id="${result.session_id}">
                    ❌ Cerrar Juego
                </button>
            `);

            // Ocultar ambos botones
            $container.find('.show-iframe, .show-iframe-direct').hide();
            $container.append($closeBtn).append($iframe);

            console.log('Sesión iniciada:', result.session_id);
            console.log('Movimiento contable:', result.move_id);

        }).catch((error) => {
            console.error('Error al iniciar juego:', error);
            alert('Error al conectar con el servidor');
            $btn.text('🎯 Jugar (Con Registro)');
            $btn.prop('disabled', false);
        });
    },

    _startGameDirect: function(iframeUrl, $container, $btn) {
        // Crear iframe directamente sin llamar al controlador
        const $iframe = $(`
            <iframe src="${iframeUrl}" 
                    width="100%" 
                    height="500px" 
                    frameborder="0"
                    allowfullscreen
                    style="border:1px solid #ddd; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            </iframe>
        `);
        
        // Agregar botón de cerrar simple
        const $closeBtn = $(`
            <button class="btn btn-sm btn-outline-secondary mb-2 close-iframe" 
                    style="float: right;">
                ❌ Cerrar Juego
            </button>
        `);

        // Ocultar ambos botones
        $container.find('.show-iframe, .show-iframe-direct').hide();
        $container.append($closeBtn).append($iframe);
    },

    _closeGame: function($container, $btn) {
        const sessionId = $btn.data('session-id');
        
        if (sessionId) {
            // Llamar al controlador para finalizar sesión
            rpc('/casino/end_game', {
                session_id: sessionId
            }).then((result) => {
                console.log('Sesión finalizada:', result);
            });
        }

        // Remover iframe y botón de cerrar
        $container.find('iframe, .close-iframe').remove();
        
        // Mostrar ambos botones originales
        $container.find('.show-iframe').show().text('🎯 Jugar (Con Registro)').prop('disabled', false);
        $container.find('.show-iframe-direct').show().text('🚀 Jugar Directo').prop('disabled', false);
    },

    _closeGameDirect: function($container, $btn) {
        // Remover iframe y botón de cerrar (sin llamar controlador)
        $container.find('iframe, .close-iframe').remove();
        
        // Mostrar ambos botones originales
        $container.find('.show-iframe').show().text('🎯 Jugar (Con Registro)').prop('disabled', false);
        $container.find('.show-iframe-direct').show().text('🚀 Jugar Directo').prop('disabled', false);
    },

    _onCloseIframe: function (ev) {
        ev.preventDefault();
        const $closeBtn = $(ev.currentTarget);
        const $container = $closeBtn.parent();
        const sessionId = $closeBtn.data('session-id');
        
        if (sessionId) {
            // Finalizar sesión si existe
            rpc('/casino/end_game', {
                session_id: sessionId
            }).then((result) => {
                console.log('Sesión finalizada:', result);
            });
        }

        // Remover iframe y botón de cerrar
        $container.find('iframe, .close-iframe').remove();
        
        // Mostrar ambos botones originales
        $container.find('.show-iframe, .show-iframe-direct').show();
        $container.find('.show-iframe').text('🎯 Jugar (Con Registro)').prop('disabled', false);
        $container.find('.show-iframe-direct').text('🚀 Jugar Directo').prop('disabled', false);
    },
});

export default publicWidget.registry.ProductIframe;