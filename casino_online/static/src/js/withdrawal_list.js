/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { deserializeDateTime } from "@web/core/l10n/dates";

publicWidget.registry.CasinoWithdrawalList = publicWidget.Widget.extend({
    selector: "[name='o_casino_withdrawal_list_container']",
    events: {
        "click .o_withdrawal_pagination_move": "_onStepWithdrawalTable",
    },

    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.partnerId = null;
        this.withdrawalData = [];
        this.maxPageContent = 10;
        this.pageOffset = 0;
    },

    async start() {
        this.maxCount = 0;
        this.withdrawalTable = $(".o_withdrawal_list_table");
        await this._super(...arguments);
        try {
            this.partnerId = this.$el.data("partner-id");
            // console.log("Withdrawal Partner ID:", this.partnerId);
            if (!this.partnerId) return;

            await this._fetchWithdrawalData().then((withdrawals) => {
                // this.withdrawals = withdrawals;
                this._renderWithdrawalTable();
                this._bindWithdrawalFormEvents();
                this.loadWithdrawalContainer();
            });
        } catch (error) {
            console.error("Error en start():", error);
        }
    },

    _onStepWithdrawalTable(ev) {
        ev.preventDefault();
        const paginationButton = $(ev.currentTarget);
        if (paginationButton.hasClass("step")) {
            this.pageOffset = parseInt(paginationButton.data("offset-step"));
        } else {
            const sign = paginationButton.hasClass("forward") ? 1 : -1;
            this.pageOffset += this.maxPageContent * sign;
        }

        this._fetchWithdrawalData();
        this._loadWithdrawalPagination();
    },

    async _fetchWithdrawalData() {
        this.withdrawalData = await this.orm.call(
            "casino.game.withdrawals",
            "search_read",
            [[["partner_id", "=", this.partnerId]]],
            { fields: ["partner_id", "bank_id", "description", "amount", "date", "state"] }
        );
        console.log("Fetching withdrawals for partner:", this.partnerId, this.withdrawalData);

        // Obtener todos los bank_id distintos
        const withdrawalIds = this.withdrawalData
            .map(w => w.bank_id && w.bank_id[0])
            .filter(id => id);
        console.log("Bank IDs to fetch:", withdrawalIds);

        if (withdrawalIds.length > 0) {
            // Segunda llamada al modelo de retiros
            console.log("Fetching bank details for IDs:", withdrawalIds);
            const withdrawals = await this.orm.call(
                "casino.game.bank",
                "read",
                [withdrawalIds, ["cuil", "bank_name", "cbu"]]
            );
            // Armar un diccionario {id: withdrawal}
            const withdrawalMap = {};
            for (const w of withdrawals) {
                console.log("Fetched bank details for ID:", w.id);
                withdrawalMap[w.id] = w;
            }

            // Enriquecer withdrawals con info del banco
            this.withdrawalData = this.withdrawalData.map(w => {
                const bank = withdrawalMap[w.bank_id && w.bank_id[0]];
                return {
                    ...w,
                    bank_cuil: bank ? bank.cuil : "",
                    bank_name: bank ? bank.bank_name : "",
                    bank_cbu: bank ? bank.cbu : "",
                };
            });
        }
        this.maxCount = this.withdrawalData.length;
    },

    _renderWithdrawalTable() {
        const container = this.$el.find(".o_casino_withdrawals_table_body");
        container.empty();

        if (this.withdrawalData.length === 0) {
            container.append(`
            <tr>
                <td colspan="7" class="text-center">
                    <h5>No hay retiros asociados</h5>
                </td>
            </tr>
        `);
            return;
        }

        // Obtener la "página" de datos
        const withdrawals = this.withdrawalData.slice(
            this.pageOffset,
            this.pageOffset + this.maxPageContent
        );

        for (const withdrawal of withdrawals) {
            container.append(`
            <tr>
                <td>${withdrawal.bank_cuil}</td>
                <td>${withdrawal.description}</td>
                <td>${withdrawal.bank_cbu}</td>
                <td>${withdrawal.amount}</td>
                <td>${this._formatDate(withdrawal.date)}</td>
                <td class="text-center">${this._stateBadgeHTML(withdrawal.state)}</td>
            </tr>
        `);
        }
    },

    _renderWithdrawalTable1() {
        const container = this.$el.find(".o_casino_withdrawals_table_body");
        console.log("Container _renderWithdrawalTable:", container);
        container.empty();
        console.log("Withdrawals Data _renderWithdrawalTable:", this.withdrawalData);
        if (this.withdrawalData.length === 0) {
            console.log("No withdrawals found");
            container.append(`
                <tr>
                <td colspan="4" class="text-center">
                    <h5>No hay retiros asociados</h5>
                </td>
                </tr>
            `);
            return;
        }
        const withdrawals = this.withdrawalData[this.pageOffset];
        console.log("Cargando Withdrawals Data _renderWithdrawalTable:", this.withdrawalData);
        for (const withdrawal of withdrawals) {
            container.append(`
                <tr>
                <td>${withdrawal.partner_id[1]}</td>
                <td>${withdrawal.bank_cuil}</td>
                <td>${withdrawal.bank_name}</td>
                <td>${withdrawal.bank_cbu}</td>
                <td>${withdrawal.amount}</td>
                <td>${withdrawal.date}</td>
                <td class="text-center">${this._stateBadgeHTML(withdrawal.state)}</td>
                </tr>
            `);
        }
    },

    _bindWithdrawalFormEvents() {
        const form = this.$el.find(".o_withdrawal_form");
        console.log("Binding form events withdrawal", form);
        form.on("submit", async (ev) => {
            ev.preventDefault();

            form[0].reset(); // Limpia el formulario
            await this._fetchWithdrawalData(); // Refresca datos
            this._renderWithdrawalTable(); // Re-renderiza tabla
        });
    },

    loadWithdrawalContainer() {
        this._renderWithdrawalTable() //this._loadTransactionTable();
        this._loadWithdrawalPagination();
    },

    _loadWithdrawalPagination() {
        const withdrawalPagination = $(".o_withdrawal_list_pagination");
        if (!withdrawalPagination.is(":empty")) withdrawalPagination.empty();

        const totalPages = Math.ceil(this.maxCount / this.maxPageContent);
        const currentPage = Math.floor(this.pageOffset / this.maxPageContent) + 1;

        // Botón "Anterior"
        withdrawalPagination.append(`
        <li class="page-item ${currentPage === 1 ? "disabled" : ""}">
            <a class="page-link o_withdrawal_pagination_move backward" href="#" aria-label="Anterior">
                <span aria-hidden="true">&laquo;</span>
            </a>
        </li>
    `);

        // Números de páginas
        for (let i = 1; i <= totalPages; i++) {
            withdrawalPagination.append(`
            <li class="page-item ${i === currentPage ? "active" : ""}">
                <a class="page-link o_withdrawal_pagination_move step" 
                   data-offset-step="${(i - 1) * this.maxPageContent}" href="#">${i}</a>
            </li>
        `);
        }

        // Botón "Siguiente"
        withdrawalPagination.append(`
        <li class="page-item ${currentPage === totalPages ? "disabled" : ""}">
            <a class="page-link o_withdrawal_pagination_move forward" href="#" aria-label="Siguiente">
                <span aria-hidden="true">&raquo;</span>
            </a>
        </li>
    `);

        this._loadWithdrawalPaginationInfo();
    },

    _loadWithdrawalPaginationInfo() {
        const withdrawalFooter = $(".o_withdrawal_list_pagination_info");
        if (!withdrawalFooter.is(":empty")) withdrawalFooter.empty();

        if (this.withdrawalData.length === 0) {
            withdrawalFooter.append("No hay retiros");
            return;
        }

        const start = this.pageOffset + 1;
        const end = Math.min(this.pageOffset + this.maxPageContent, this.maxCount);
        const displayText = `Mostrando ${start}-${end} de ${this.maxCount} retiros`;

        withdrawalFooter.append(displayText);
    },

    // Dentro de CasinoWithdrawalList
    _stateBadgeHTML(state) {
        const MAP = {
            approved: {
                label: "Aprobado",
                icon: '<i class="fa fa-check-circle" aria-hidden="true"></i>',
                cls: "status-badge status-approved",
            },
            pending: {
                label: "Pendiente",
                icon: '<i class="fa fa-hourglass-half" aria-hidden="true"></i>',
                cls: "status-badge status-pending",
            },
            rejected: {
                label: "Rechazado",
                icon: '<i class="fa fa-times-circle" aria-hidden="true"></i>',
                cls: "status-badge status-rejected",
            },
        };
        const m = MAP[state] || {
            label: state || "Desconocido",
            icon: '<i class="fa fa-question-circle" aria-hidden="true"></i>',
            cls: "status-badge status-unknown",
        };

        // Solo ícono visible; el texto va oculto para accesibilidad
        return `
            <span class="${m.cls}" title="${m.label}">
            ${m.icon}
            <span class="visually-hidden">${m.label}</span>
            </span>
        `;
    },

    _formatDate(dtStr) {
        if (!dtStr) return "";
        // deserializeDateTime devuelve un Luxon DateTime ya en la zona del usuario
        const dt = deserializeDateTime(dtStr);
        return dt ? dt.toFormat("dd-LL-yyyy HH:mm:ss") : "";
    }
});

export default publicWidget.registry.CasinoWithdrawalList;
