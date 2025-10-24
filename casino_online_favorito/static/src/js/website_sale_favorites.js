odoo.define('casino_online_favorito.casino_online_favorito', function (require) {
'use strict';

var publicWidget = require('web.public.widget');
var rpc = require('web.rpc');
var Dialog = require('web.Dialog');
var core = require('web.core');
var _t = core._t;

publicWidget.registry.WebsiteSaleFavorites = publicWidget.Widget.extend({
    selector: '#wrapwrap', // Attach to a global element
    events: {
        'click .o_wsf_toggle': '_onToggleFavorite',
    },

    /**
     * @override
     */
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            self._initFavorites();
        });
    },

    _initFavorites: function () {
        var self = this;
        // Selectors to find product containers
        var productSelectors = [
            '[data-oe-model="product.template"]',
            '.oe_product',
            '[data-product-template-id]',
            '.o_wsale_product_grid_wrapper [itemscope]'
        ];

        var $productItems = this.$(productSelectors.join(', ')).filter(':not(.favorite-processed)');
        if (!$productItems.length) {
            return;
        }

        var productData = [];
        $productItems.each(function () {
            var $item = $(this);
            let productId = $item.data('oe-id') ||
                            $item.data('product-template-id') ||
                            $item.data('product-id');
            if (!productId) {
                const productLink = $item.find('a[href*="/shop/product/"]');
                if (productLink.length) {
                    const match = productLink.attr('href').match(/\/shop\/product\/(\d+)/);
                    if (match) productId = match[1];
                }
            }
            if (productId) {
                // Ensure we don't process the same item twice
                if ($item.find('.o_wsf_container').length === 0) {
                    productData.push({ item: $item, productId: parseInt(productId) });
                    $item.addClass('favorite-processed');
                }
            }
        });

        var productIds = [...new Set(productData.map(p => p.productId))];
        if (!productIds.length) {
            return;
        }

        // Get initial status for all products
        rpc.query({
            route: '/shop/favorites/status',
            params: { product_ids: productIds }
        }).then(function (favoritesStatus) {
            productData.forEach(function (p) {
                var isFavorited = favoritesStatus[p.productId] === true;
                self._renderButton(p.item, p.productId, isFavorited);
            });
        });
    },

    _renderButton: function ($container, productId, isFavorited) {
        var $button = $(core.qweb.render('casino_online_favorito.favorite_button_snippet', {
            product_id: productId
        }));

        // Set initial state
        this._updateButtonUI($button.find('.o_wsf_toggle'), isFavorited);

        // Append button
        if ($container.css('position') === 'static') {
            $container.css('position', 'relative');
        }
        $container.append($button);
    },

    _updateButtonUI: function ($btn, isFavorited) {
        var $icon = $btn.find('.o_wsf_icon');
        var titleOn = $btn.data('title-on');
        var titleOff = $btn.data('title-off');

        if (isFavorited) {
            $btn.addClass('favorited');
            $icon.removeClass('fa-heart-o').addClass('fa-heart');
            $btn.attr('title', titleOn);
        } else {
            $btn.removeClass('favorited');
            $icon.removeClass('fa-heart').addClass('fa-heart-o');
            $btn.attr('title', titleOff);
        }
    },

    _onToggleFavorite: function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        var self = this;
        var $btn = $(ev.currentTarget);
        var productId = $btn.data('product-id');

        $btn.prop('disabled', true);

        rpc.query({
            route: '/shop/favorite/toggle',
            params: { product_id: productId }
        }).then(function (result) {
            if (result.error) {
                if (result.error === 'not_logged_in') {
                    Dialog.confirm(self, _t('You must be logged in to manage your favorites. Do you want to log in?'), {
                        confirm_callback: function () {
                            window.location.href = '/web/login?redirect=' + encodeURIComponent(window.location.pathname);
                        },
                    });
                }
                return;
            }
            self._updateButtonUI($btn, result.favorited);
        }).always(function () {
            $btn.prop('disabled', false);
        });
    },
});

return publicWidget.registry.WebsiteSaleFavorites;
});