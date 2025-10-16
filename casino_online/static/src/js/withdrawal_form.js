/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CasinoWithdrawalForm = publicWidget.Widget.extend({
    selector: "#withdrawal_methods_container",

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.partnerId = null;
        this.selectedMethod = "transfer"; // default
    },

    async start() {
        await this._super(...arguments);
        this.partnerId = this.$el.data("partner-id");
        console.log("Iniciando el formulario de retiro con el partner ", this.partnerId);

        const modal = $("#withdrawalTransferModal");
        modal.on("show.bs.modal", (ev) => {
            const opener = ev.relatedTarget; // card que disparó el modal
            const method = opener ? opener.getAttribute("data-method") : null;
            this.selectedMethod = method || "transfer";
            modal.data("method", this.selectedMethod);

            this._toggleBankRow(method);

            modal.find(".modal-title").text(
                this.selectedMethod === "transfer"
                    ? "Solicitud de Retiro por Transferencia"
                    : "Solicitud de Retiro en Casa Central"
            );
        });

        this._bindModalSubmit();
    },

    _toggleBankRow(method) {
        const modal = $("#withdrawalTransferModal");
        const $group = modal.find(".o_bank_row");
        const $select = modal.find("#bank_account_select");

        const hide = method === "cashier"; // Casa Central -> ocultar
        $group.toggleClass("d-none", hide);
        $select.prop("disabled", hide);    // evita que se envíe/valide
        if (hide) $select.val("");         // limpia selección si estaba marcada
    },

    _bindModalSubmit() {
        const modal = $("#withdrawalTransferModal");
        const form = modal.find(".o_withdrawal_form");
        const submitBtn = modal.find(".o_withdrawal_submit");
        console.log("Formulario de retiro listo");
        submitBtn.on("click", async () => {
            const amount = parseFloat(form.find("[name='amount']").val());
            const password = form.find("[name='password']").val().trim();
            const method = modal.data("method") || this.selectedMethod || "transfer";

            // bank_id solo requerido si es transferencia
            const bankId = form.find("[name='bank_account']").val();

            if (!amount || !password || (method === "transfer" && !bankId)) {
                alert("Complete todos los campos.");
                return;
            }

            const description =
                method === "transfer" ? "Extracción por Transferencia" : "Retiro en Casa Central";
            try {
                const transaction_id = "TX-" + Date.now();
                const d = new Date();
                const dateTime = d.getFullYear() + '-' +
                    String(d.getMonth() + 1).padStart(2, '0') + '-' +
                    String(d.getDate()).padStart(2, '0') + ' ' +
                    String(d.getHours()).padStart(2, '0') + ':' +
                    String(d.getMinutes()).padStart(2, '0') + ':' +
                    String(d.getSeconds()).padStart(2, '0');
                await this.orm.call("casino.game.withdrawals", "create", [{
                    transaction_id,
                    date: dateTime,
                    description,
                    amount,
                    state: "pending",
                    partner_id: this.partnerId,
                    bank_id: method === "transfer" ? parseInt(bankId) : null,
                }]);
                if (method === "transfer") vals.bank_id = parseInt(bankId);

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
