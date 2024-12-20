/** @odoo-module **/

import { Component } from '@odoo/owl';
import { registry } from '@web/core/registry';

export class Transfer_accounts extends Component {
  static template = 'billetera_pagoflex.Transfer_accounts';
  setup() {}
}

registry
  .category('public_components')
  .add('billetera_pagoflex.Transfer_accounts', Transfer_accounts);
