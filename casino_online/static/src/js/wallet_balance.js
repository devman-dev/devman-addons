/** @odoo-module **/
import { useService } from "@web/core/utils/hooks";
import { onWillStart, onWillUnmount } from "@odoo/owl";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.CasinoWalletBalance = publicWidget.Widget.extend({
  selector: ".o_casino_wallet_balance",
  async start() {
    console.log("Lanzamiento de Notification");
    this.rpc = this.bindService("rpc");
    this.bus = this.bindService("bus_service");
    this.partnerId = parseInt(this.el.dataset.partnerId, 10);
    this.bus.addChannel("casino_wallet_update");
    this.bus.addEventListener("notification", this._onNotification.bind(this));
    this.bus.start();
    return this._super(...arguments);
  },
  async _onNotification(ev) {
    console.log("Notification received:", ev);
    for (const { type, payload } of ev.detail) {
      if (type === "casino_wallet_update" && payload.partner_id === this.partnerId) {
        this.el.textContent = payload.balance.toFixed(2);
      }
    }
  },
});
