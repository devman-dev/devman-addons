/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CasinoWithdrawalForm = publicWidget.Widget.extend({
    selector: "#withdrawal_methods_container",

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.partnerId = null;
        this.selectedMethod = "transfer";
        // Variable para evitar recargar bancos innecesariamente
        this.banksLoaded = false;
    },

    async start() {
        await this._super(...arguments);
        this.partnerId = this.$el.data("partner-id");

        const $modal = $("#withdrawalTransferModal");

        // 1. Configuración visual al abrir el modal
        $modal.on("show.bs.modal", async (ev) => {
            const opener = ev.relatedTarget;
            const method = opener ? opener.getAttribute("data-method") : null;
            this.selectedMethod = method || "transfer";
            $modal.data("method", this.selectedMethod);

            this._toggleBankRow(method);

            $modal.find(".modal-title").text(
                this.selectedMethod === "transfer"
                    ? "Solicitud de Retiro por Transferencia"
                    : "Solicitud de Retiro en Casa Central"
            );

            this._hideMessage();

            // NUEVO: Si es transferencia, cargamos los bancos
            if (this.selectedMethod === "transfer") {
                await this._loadBankAccounts();
            }
        });

        // 2. Delegación de eventos para el botón Submit
        $modal.off("click", ".o_withdrawal_submit").on("click", ".o_withdrawal_submit", async (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            await this._onSubmitWithdrawal(ev);
        });
    },

    // === NUEVA FUNCIÓN PARA CARGAR BANCOS ===
    async _loadBankAccounts() {
        const $select = $("#bank_account_select");

        // Si ya tiene opciones cargadas (más de 1, contando el placeholder), no recargamos
        // Quita este if si prefieres que siempre refresque la lista
        if (this.banksLoaded && $select.children('option').length > 1) {
            return;
        }

        try {
            // Ponemos estado de carga
            $select.html('<option value="">Cargando cuentas...</option>');
            $select.prop('disabled', true);

            // Usamos fetch al controlador que tenías definido originalmente
            const response = await fetch('/casino/withdrawal/banks', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {}
                })
            });

            const data = await response.json();
            const banks = data.result || [];

            // Limpiamos y llenamos el select
            $select.empty();
            $select.append('<option value="">Seleccione una cuenta</option>');

            if (banks.length === 0) {
                $select.append('<option value="" disabled>No hay cuentas registradas</option>');
            } else {
                banks.forEach(function (bank) {
                    // Asegúrate de que tu controlador devuelve id, name y cbu
                    const option = $('<option>').val(bank.id).text(`${bank.name} - ${bank.cbu || 'Sin CBU'}`);
                    $select.append(option);
                });
                this.banksLoaded = true;
            }

        } catch (error) {
            console.error("Error cargando bancos:", error);
            $select.html('<option value="">Error al cargar cuentas</option>');
        } finally {
            $select.prop('disabled', false);
        }
    },

    async _onSubmitWithdrawal(ev) {
        const modal = $("#withdrawalTransferModal");
        const form = modal.find(".o_withdrawal_form");

        const amountVal = form.find("[name='amount']").val();
        const amount = amountVal ? parseFloat(amountVal) : 0;
        const password = form.find("[name='password']").val().trim();
        const method = modal.data("method") || this.selectedMethod || "transfer";
        const bankId = form.find("[name='bank_account']").val();

        this._hideMessage();

        // Validaciones Frontend
        if (amount <= 0) {
            this._showMessage("El monto debe ser mayor a 0.", 'warning');
            return;
        }
        if (!password) {
            this._showMessage("Ingrese su contraseña.", 'warning');
            return;
        }
        if (method === "transfer" && !bankId) {
            this._showMessage("Seleccione una cuenta bancaria.", 'warning');
            return;
        }

        const $btn = $(ev.currentTarget);
        $btn.prop('disabled', true);

        try {
            // 1. VALIDACIÓN DE CONTRASEÑA
            const response = await fetch('/casino/withdrawal/validate_password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: { password: password },
                    id: Date.now()
                }),
            });
            const resultJson = await response.json();

            if (resultJson.error) {
                throw new Error(resultJson.error.data?.message || "Error RPC");
            }

            const result = resultJson.result;
            if (!result || !result.success) {
                this._showMessage(result?.message || 'Contraseña inválida', 'danger');
                $btn.prop('disabled', false);
                return;
            }

            // 2. CREACIÓN DEL RETIRO
            const description = method === "transfer" ? "Extracción por Transferencia" : "Retiro en Casa Central";
            const now = new Date();
            const dateTime = now.toISOString().slice(0, 19).replace('T', ' ');
            const transaction_id = "TX-" + now.getTime();

            await this.orm.call("casino.game.withdrawals", "create", [{
                transaction_id: transaction_id,
                date: dateTime,
                description: description,
                amount: amount,
                state: "pending",
                partner_id: parseInt(this.partnerId),
                bank_id: method === "transfer" ? parseInt(bankId) : null,
                operation_type: "withdrawal",
            }]);

            this._showMessage("Solicitud enviada correctamente.", 'success');
            form[0].reset();

            setTimeout(() => {
                modal.modal("hide");
                $btn.prop('disabled', false);
                // Si quieres que recargue la página:
                // window.location.reload();
            }, 2000);

        } catch (error) {
            console.error("Error proceso retiro:", error);
            this._showMessage("Hubo un error técnico. Intente más tarde.", 'danger');
            $btn.prop('disabled', false);
        }
    },

    _toggleBankRow(method) {
        const modal = $("#withdrawalTransferModal");
        const $group = modal.find(".o_bank_row");
        const $select = modal.find("#bank_account_select");
        const hide = method === "cashier";

        $group.toggleClass("d-none", hide);
        $select.prop("disabled", hide);
        if (hide) $select.val("");
    },

    _showMessage(message, type = 'danger') {
        const modal = $("#withdrawalTransferModal");
        const container = modal.find(".o_withdrawal_message_container");
        const alertDiv = container.find(".alert");

        alertDiv.removeClass('alert-danger alert-success alert-warning alert-info');
        alertDiv.addClass(`alert-${type}`);
        container.find(".o_withdrawal_message_text").text(message);
        container.removeClass('d-none');
    },

    _hideMessage() {
        $("#withdrawalTransferModal").find(".o_withdrawal_message_container").addClass('d-none');
    },
});

export default publicWidget.registry.CasinoWithdrawalForm;