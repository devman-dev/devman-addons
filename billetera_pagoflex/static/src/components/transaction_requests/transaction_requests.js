/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { session } from '@web/session';

export class Wallet_transfer_request extends Component {
    static template = 'billetera_pagoflex.Wallet_transfer_request';

    setup() {
        this.state = useState({
            transactions_filter: [],
            transactions_filter2: [],
            state_filter: 'all',
            state_filter2: 'all',
        });
        this.user_id = session.user_id;

        onWillStart(async () => {
            await this.onShowTransactionsAll();
        });
    }


    async onShowTransactionsAll() {
         try {
            this.state.state_filter = 'all';
            const result = await this.env.services.orm.searchRead(
                'transfer.request',
                [['customer.user_ids', 'in', this.user_id]],
                ['amount', 'date','transfer_request_state','alias_destination_account', 'description', 'id'],
                { limit: 10 }
            );

            if (result.length > 0) {
                this.state.transactions_filter = result
            } else {
                this.state.transactions_filter = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter = [];
        }
    }
}

registry.category('public_components').add('billetera_pagoflex.Wallet_transfer_request', Wallet_transfer_request);
