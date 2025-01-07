/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { session } from '@web/session';

export class Wallet_filters extends Component {
    static template = 'billetera_pagoflex.Wallet_filters';

    setup() {
        this.state = useState({
            transactions: [],
        });
        this.user_id = session.user_id;

        onWillStart(async () => {
            await this.onShowTransactionsPending('pendiente');
        });
    }

    async onShowTransactionsPending() {
        try {
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'pendiente']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type'], 10, 10
            );

            if (result.length > 0) {
                this.state.transactions = result
            } else {
                this.state.transactions = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions = [];
        }
    }
    async onShowTransactionsRefused() {
        try {
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'rechazado']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type'], 10, 10
            );

            if (result.length > 0) {
                this.state.transactions = result
            } else {
                this.state.transactions = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions = [];
        }
    }

}

registry.category('public_components').add('billetera_pagoflex.Wallet_filters', Wallet_filters);
