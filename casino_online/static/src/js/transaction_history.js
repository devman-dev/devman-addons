/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { formatCurrency } from "@web/core/currency";
import { Component } from "@odoo/owl";

const paymentState = {
  draft: ["Borrador", "bg-info"],
  in_process: ["En Proceso", "bg-warning"],
  paid: ["Pagado", "bg-success"],
  cancelled: ["Cancelada", ""],
  rejected: ["Rechazado", ""],
};

publicWidget.registry.TransactionHistory = publicWidget.Widget.extend({
  selector: "[name='o_transaction_list_container']",
  events: {
    "click .o_transaction_pagination_move": "_onStepTransactionTable",
  },

  init() {
    this._super(...arguments);
    this.orm = this.bindService("orm");

    this.maxPageContent = 8;
    this.pageOffset = 0;
  },
  async start() {
    await this._super(...arguments);
    this.content = $(this)[0].$el;
    this.resModel = "account.payment";
    this.partnerId = this.content.data("partner-id");
    this.currencyId = this.content.data("currency-id");
    this.transactionData = {};
    this.maxCount = 0;
    this.transactionTotalOffset = 0.0;
    this.transactionTable = $(".o_transaction_list_table");
    await this._loadTransactionData();

    this.loadTransactionContainer();
  },
  loadTransactionContainer() {
    this._loadTransactionTable();
    this._loadTransactionPagination();
  },
  _loadTransactionTable() {
    const transactionBody = this.transactionTable.find(
      ".o_transaction_list_content"
    );
    const transactionFooter = this.transactionTable.find(
      ".o_transaction_list_footer"
    );

    if (Object.keys(this.transactionData).length === 0) {
      transactionBody.append(
        `<tr>
          <td class="text-center" colspan="4">
            <h4>¡No se han hecho depósitos todavía!</h4>
          </td>
        </tr>`
      );
      transactionFooter
        .find(".o_transaction_list_total")
        .append(`${formatCurrency(0.0, this.currencyId)}`);
    } else {
      const transactions = this.transactionData[this.pageOffset];
      let total_per_page = 0.0;

      if (!transactionBody.is(":empty")) transactionBody.empty();

      for (let i = 0; i < transactions.length; i++) {
        total_per_page += transactions[i].amount;
        transactionBody.append(
          `<tr>
            <td class='text-center text-nowrap'>${transactions[i].date}</td>
            <td>${transactions[i].payment_reference || transactions[i].memo || "Sin referencia"}</td>
            <td class="text-end text-success fw-bold">${formatCurrency(
            transactions[i].amount,
            this.currencyId
          )}</td>
          </tr>`
        );
      }

      if (!transactionFooter.find(".o_transaction_list_total").is(":empty"))
        transactionFooter.find(".o_transaction_list_total").empty();
      transactionFooter
        .find(".o_transaction_list_total")
        .append(`${formatCurrency(total_per_page, this.currencyId)}`);
    }
  },
  _loadTransactionPaginationInfo() {
    const transactionFooter = $(".o_transaction_list_pagination_info");
    if (!transactionFooter.is(":empty")) transactionFooter.empty();

    let currentCount = 0;

    if (Object.keys(this.transactionData).length !== 0) {
      for (let i = this.pageOffset; i > -1; i -= this.maxPageContent) {
        currentCount += this.transactionData[i].length;
      }
    }

    const displayText = `Mostrando ${currentCount} de ${this.maxCount} transacciones`;
    transactionFooter.append(displayText);
  },
  _loadTransactionPagination() {
    const transactionPagination = $(".o_transaction_list_pagination");

    if (Object.keys(this.transactionData).length === 0) {
      this._loadTransactionPaginationInfo();
    } else {
      const maxTransactions = Object.entries(Object.keys(this.transactionData));

      if (!transactionPagination.is(":empty")) transactionPagination.empty();

      let init_classes = ["page-item", this.pageOffset === 0 ? "disabled" : ""];
      let end_classes = [
        "page-item",
        this.pageOffset === parseInt(maxTransactions.at(-1)[1])
          ? "disabled"
          : "",
      ];

      transactionPagination.append(
        `<li class="${init_classes.join(" ")}">
          <a class="page-link o_transaction_pagination_move backward" href="#" aria-label="Anterior">
            <span aria-hidden="true">&laquo;</span>
          </a>
        </li>`
      );
      for (let i = 0; i < maxTransactions.length; i++) {
        let class_list = [
          "page-item",
          this.pageOffset === parseInt(maxTransactions[i][1]) ? "active" : "",
        ];
        transactionPagination.append(
          `<li class="${class_list.join(" ")}">
            <a class="page-link o_transaction_pagination_move step" data-offset-step="${parseInt(
            maxTransactions[i][1]
          )}" href="#">${i + 1}</a>
          </li>`
        );
      }
      transactionPagination.append(
        `<li class="${end_classes.join(" ")}">
          <a class="page-link o_transaction_pagination_move forward" href="#" aria-label="Siguente">
            <span aria-hidden="true">&raquo;</span>
          </a>
        </li>`
      );

      this._loadTransactionPaginationInfo();
    }
  },
  _onStepTransactionTable(ev) {
    const paginationButton = $(ev.currentTarget);
    if (paginationButton.hasClass("step")) {
      this.pageOffset = parseInt(paginationButton.data("offset-step"));
    } else {
      const sign = paginationButton.hasClass("forward") ? 1 : -1;
      this.pageOffset += this.maxPageContent * sign;
    }

    this._loadTransactionTable();
    this._loadTransactionPagination();
  },
  async _loadTransactionData() {
    const paymentTransaction = await this.orm.call(
      "res.partner",
      "get_deposit_payments",
      [this.partnerId]
    );

    if (paymentTransaction.length !== 0) {
      for (let i = 0; i < paymentTransaction.length; i += this.maxPageContent) {
        const chunk = paymentTransaction.slice(i, i + this.maxPageContent);
        this.transactionData[i] = chunk;
      }
      this.maxCount = paymentTransaction.length;
    }
  },
});
export default publicWidget.registry.TransactionHistory;
