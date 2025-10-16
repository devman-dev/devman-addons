/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CasinoBankList = publicWidget.Widget.extend({
    selector: "[name='o_casino_bank_list_container']",

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.partnerId = null;
        this.bankData = [];
    },

    async start() {
        await this._super(...arguments);
        try {
            this.partnerId = this.$el.data("partner-id");
            console.log("Partner ID:", this.partnerId);
            if (!this.partnerId) return;

            await this._fetchBankData();
            this._renderBankTable();
            this._bindFormEvents();

        } catch (error) {
            console.error("Error en start():", error);
        }
    },

    async _fetchBankData() {
        this.bankData = await this.orm.call(
            "casino.game.bank",
            "search_read",
            [[["partner_id", "=", this.partnerId]]],
            { fields: ["partner_id", "cuil", "bank_name", "cbu"] }
        );
    },

    _renderBankTable() {
        const container = this.$el.find(".o_casino_bank_table_body");
        container.empty();

        if (this.bankData.length === 0) {
            container.append(`
        <tr>
          <td colspan="4" class="text-center">
            <h5>No hay cuentas bancarias asociadas</h5>
          </td>
        </tr>
      `);
            return;
        }
        console.log("Banks Data _renderBankTable:", this.bankData);

        for (const bank of this.bankData) {
            container.append(`
        <tr>
          <td>${bank.partner_id[1]}</td>
          <td>${bank.cuil}</td>
          <td>${bank.bank_name}</td>
          <td>${bank.cbu}</td>
        </tr>
      `);
        }
    },

    _bindFormEvents() {
        const form = this.$el.find(".o_casino_bank_form");
        console.log("Binding form events", form);
        form.on("submit", async (ev) => {
            ev.preventDefault();

            const bank_name = form.find("[name='bank_name']").val().trim();
            const cbu = form.find("[name='cbu']").val().trim();
            const cuil = form.find("[name='cuil']").val().trim();
            const partner = this.partnerId;
            console.log("Form Data:", { partner, bank_name, cbu, cuil });
            if (!bank_name || !cbu || !cuil) return;

            await this.orm.call("casino.game.bank", "create", [{
                partner_id: this.partnerId,
                bank_name,
                cbu,
                cuil,
            }]);

            form[0].reset(); // Limpia el formulario
            await this._fetchBankData(); // Refresca datos
            this._renderBankTable(); // Re-renderiza tabla
        });
    },
});

export default publicWidget.registry.CasinoBankList;
