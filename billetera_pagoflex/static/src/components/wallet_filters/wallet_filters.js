/** @odoo-module **/

// Importación de módulos necesarios de Odoo OWL
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from '@web/core/registry';
import { session } from '@web/session';

// Definición de la clase Wallet_filters que extiende de Component
export class Wallet_filters extends Component {
    // Especifica la plantilla que se utilizará para este componente
    static template = 'billetera_pagoflex.Wallet_filters';

    // Método de configuración del componente
    setup() {
        // Definición del estado inicial del componente
        this.state = useState({
            transactions: [],
            transactions_filter2: [],
            state_filter: 'pending',
            state_filter2: 'all',
        });
        // Obtención del ID del usuario de la sesión actual
        this.user_id = session.user_id;

        // Ejecutar funciones al iniciar el componente
        onWillStart(async () => {
            await this.onShowTransactionsPending();
            await this.onShowTransactionsApproved();
        });
    }

    // Método para mostrar transacciones pendientes
    async onShowTransactionsPending() {
        try {
            this.state.state_filter2 = 'pending';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'pendiente']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type', 'is_commission'],
                { limit: 5 }
            );

            if (result.length > 0) {
                this.state.transactions_filter2 = result;
            } else {
                this.state.transactions_filter2 = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter2 = [];
        }
    }

    // Método para mostrar transacciones rechazadas
    async onShowTransactionsRefused() {
        try {
            this.state.state_filter = 'refused';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'rechazado']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type', 'is_commission'], { limit: 10 }
            );

            if (result.length > 0) {
                this.state.transactions_filter = result;
            } else {
                this.state.transactions_filter = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter = [];
        }
    }

    // Método para mostrar transacciones aprobadas
    async onShowTransactionsApproved() {
        try {
            this.state.state_filter2 = 'approved';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id], ['transaction_state', '=', 'aprobado']],
                ['amount', 'date', 'transaction_state', 'collection_trans_type', 'is_commission'], { limit: 5 }
            );

            if (result.length > 0) {
                this.state.transactions_filter2 = result;
            } else {
                this.state.transactions_filter2 = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter2 = [];
        }
    }

    // Método para mostrar todas las transacciones
    async onShowTransactionsAll() {
        try {
            this.state.state_filter2 = 'all';
            const result = await this.env.services.orm.searchRead(
                'collection.transaction',
                [['customer.user_ids', 'in', this.user_id]],
                ['amount', 'date', 'transaction_state', 'collection_trans_type', 'is_commission'], 
                { limit: 5 }
            );

            if (result.length > 0) {
                this.state.transactions_filter2 = result;
            } else {
                this.state.transactions_filter2 = [];
            }
        } catch (error) {
            console.error('ERROR!', error);
            this.state.transactions_filter2 = [];
        }
    }
}

// Registro del componente en la categoría 'public_components'
registry.category('public_components').add('billetera_pagoflex.Wallet_filters', Wallet_filters);