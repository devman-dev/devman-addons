/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CasinoWithdrawalForm = publicWidget.Widget.extend({
    selector: "#withdrawal_methods_container",

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.partnerId = null;
    },

    async start() {
        await this._super(...arguments);
        this.partnerId = this.$el.data("partner-id");
        console.log("Iniciando el formulario de retiro con el partner ", this.partnerId);
        this._bindModalSubmit();
    },

    _bindModalSubmit() {
        const modal = $("#withdrawalTransferModal");
        const form = modal.find(".o_withdrawal_form");
        const submitBtn = modal.find(".o_withdrawal_submit");
        console.log("Formulario de retiro listo");
        submitBtn.on("click", async () => {
            const amount = parseFloat(form.find("[name='amount']").val());
            const password = form.find("[name='password']").val().trim();
            const bankId = form.find("[name='bank_account']").val();

            if (!amount || !password) {
                alert("Complete todos los campos.");
                return;
            }

            try {
                const transaction_id = "TX-" + Date.now();
                await this.orm.call("casino.game.withdrawals", "create", [{
                    transaction_id,
                    date: new Date().toISOString(),
                    description: "Extracción por Transferencia",
                    amount,
                    state: "pending",
                    partner_id: this.partnerId,
                    bank_id: parseInt(bankId),
                }]);

                alert("Solicitud enviada correctamente.");
                form[0].reset();
                modal.modal("hide");
            } catch (error) {
                console.error("Error creando retiro:", error);
                modal.modal("hide");
                // alert("Hubo un error al enviar la solicitud.");
            }
        });
    },
});

export default publicWidget.registry.CasinoWithdrawalForm;
