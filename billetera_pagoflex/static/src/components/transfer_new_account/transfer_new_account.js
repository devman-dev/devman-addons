/** @odoo-module **/

import { Component } from '@odoo/owl';
import { registry } from '@web/core/registry';

export class Transfer_new_accounts extends Component {
  static template = 'billetera_pagoflex.Transfer_new_account';
  setup() {}
}

registry
  .category('public_components')
  .add('billetera_pagoflex.Transfer_new_account', Transfer_new_accounts);
