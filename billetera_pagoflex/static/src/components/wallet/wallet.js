/** @odoo-module **/

import { Component, useState, onWillStart } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { session } from '@web/session';

export class Wallet extends Component {
  static template = 'billetera_pagoflex.Wallet';
  setup() {
    this.state = useState({
      available_balance: 0,
    });
    this.user_id = session.user_id;

    onWillStart(async () => await this.getAvailableBalance());
  }

  async getAvailableBalance() {
    try {
      const result = await this.env.services.orm.searchRead(
        'collection.dashboard.customer',
        [['customer.user_ids', 'in', this.user_id]],
        ['customer_available_balance']
      );

      if (result.length > 0) {
        const rawBalance = result[0].customer_available_balance || 0;
        this.state.available_balance = new Intl.NumberFormat('es-AR', {
          style: 'decimal',
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(rawBalance);
      } else {
        this.state.available_balance = 0;
      }
    } catch (error) {
      console.error('ERROR!', error);
      this.state.available_balance = 0;
    }
  }
}

registry.category('public_components').add('billetera_pagoflex.Wallet', Wallet);
