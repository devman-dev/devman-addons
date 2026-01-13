/** @odoo-module **/
// import { useService } from "@web/core/utils/hooks";
// import { onWillStart, onWillUnmount } from "@odoo/owl";
// import publicWidget from "@web/legacy/js/public/public_widget";

// "@web/legacy/js/public/public_widget";
// publicWidget.registry.CasinoWalletBalance = publicWidget.Widget.extend({
//   selector: ".o_casino_wallet_balance",
//   async start() {
//     console.log("Lanzamiento de Notification");
//     this.rpc = this.bindService("rpc");
//     this.bus = this.bindService("bus_service");
//     this.partnerId = parseInt(this.el.dataset.partnerId, 10);
//     this.bus.addChannel("casino_wallet_update");
//     this.bus.addEventListener("notification", this._onNotification.bind(this));
//     this.bus.start();
//     return this._super(...arguments);
//   },
//   async _onNotification(ev) {
//     console.log("Notification received:", ev);
//     for (const { type, payload } of ev.detail) {
//       if (type === "casino_wallet_update" && payload.partner_id === this.partnerId) {
//         this.el.textContent = payload.balance.toFixed(2);
//       }
//     }
//   },
// });

import { Component, mount, onWillStart, onWillUnmount, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { formatCurrency } from "@web/core/currency";

const onReady = (cb) => {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", cb, { once: true });
  } else {
    cb();
  }
};

class CasinoWalletBalance extends Component {
  static template = xml`
    <span
      t-att-class="props.className"
      t-att-data-partner-id="props.partnerId"
      t-att-data-currency-id="props.currencyId"
      t-raw="state.html"
    />
  `;

  setup() {
    console.log("Lanzamiento de SETUP");
    this.bus = useService("bus_service");
    this.rpc = useService("rpc");
    this.state = useState({ html: this.props.initialHtml });

    this._onNotification = (ev) => {
      for (const { type, payload } of ev.detail) {
        if (type === "casino_wallet_update" && payload.partner_id === this.props.partnerId) {
          const amount = payload.balance ?? 0.0;
          this.state.html = formatCurrency(amount, this.props.currencyId);
        }
      }
    };

    // Cargar saldo actual desde BD al iniciar
    this._loadBalance = async () => {
      try {
        const result = await this.rpc("/web/dataset/call_kw", {
          model: "res.partner",
          method: "read",
          args: [[this.props.partnerId], ["balance_game"]],
          kwargs: {},
        });
        if (result && result.length > 0) {
          const balance = result[0].balance_game ?? 0.0;
          this.state.html = formatCurrency(balance, this.props.currencyId);
        }
      } catch (error) {
        console.error("Error loading balance:", error);
      }
    };

    onWillStart(async () => {
      console.log("Lanzamiento de OnWillStart");
      // Cargar saldo actual primero
      await this._loadBalance();
      // Luego configurar bus para actualizaciones en tiempo real
      this.bus.addChannel("casino_wallet_update");
      this.bus.addEventListener("notification", this._onNotification);
      this.bus.start();
    });

    onWillUnmount(() => {
      this.bus.removeEventListener("notification", this._onNotification);
    });
  }
}

onReady(() => {
  console.log("Lanzamiento de WhenReady");
  document.querySelectorAll(".o_casino_wallet_balance").forEach((el) => {
    const partnerId = parseInt(el.dataset.partnerId, 10);
    const currencyId = parseInt(el.dataset.currencyId, 10);
    console.log("Partner ID:", partnerId);
    console.log("Currency ID:", currencyId);
    mount(CasinoWalletBalance, {
      target: el,
      props: {
        partnerId,
        currencyId,
        className: el.className,
        initialHtml: el.innerHTML,
      },
    });
  });
});
