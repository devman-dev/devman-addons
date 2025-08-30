odoo.define('casino_online.withdrawal_modal', function (require) {
    "use strict";

    var publicWidget = require('web.public.widget');
    var Dialog = require('web.Dialog');

    publicWidget.registry.WithdrawalModal = publicWidget.Widget.extend({
        selector: '.o_withdrawal_transfer_button',
        events: {
            'click': '_onClick',
        },

        _onClick: function (ev) {
            ev.preventDefault();
            var self = this;
            $.get("/casino/withdrawal/form").then(function (modalHtml) {
                var $modal = $(modalHtml).appendTo('body');
                $modal.modal('show');
            });
        },
    });
});
