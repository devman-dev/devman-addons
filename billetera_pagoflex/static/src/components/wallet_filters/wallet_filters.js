/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { session } from '@web/session';

export class Wallet_filters extends Component {
    static template = 'billetera_pagoflex.Wallet_filters';

    setup() {
        this.state = useState({
            transactions_filter: [],
            transactions_filter2: [],
            state_filter: 'pending',
            state_filter2: 'aprroved'
        });
        this.user_id = session.user_id;

        onWillStart(async () => {
            await this.onShowTransactionsPending();
            await this.onShowTransactionsApproved();
        });
    }

    async onShowTransactionsPending() {
        try {
            this.state.state_filter = 'pending';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'pendiente']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type','is_commission'], 10, 10
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
    async onShowTransactionsRefused() {
        try {
            this.state.state_filter = 'refused';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'rechazado']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type','is_commission'], 10, 10
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
    async onShowTransactionsApproved() {
        try {
            this.state.state_filter2 = 'approved';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'aprobado']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type','is_commission'], 10, 10
            );

            if (result.length > 0) {
                console.log('Aprobados',result)
                this.state.transactions_filter2 = result
            } else {
                this.state.transactions_filter2 = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter2 = [];
        }
    }
    async onShowTransactionsAll() {
        try {
            this.state.state_filter2 = 'all';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id]],
                ['amount', 'date', 'transaction_state', 'collection_trans_type','is_commission'], 10, 10
            );

            if (result.length > 0) {
                console.log('Todos',result)
                this.state.transactions_filter2 = result
            } else {
                this.state.transactions_filter2 = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter2 = [];
        }
    }
}

registry.category('public_components').add('billetera_pagoflex.Wallet_filters', Wallet_filters);
