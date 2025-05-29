/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, useState } from "@odoo/owl";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class MyWidget extends Component {
    static template = "collection_payment.MyWidget";
    static props = {
        ...standardFieldProps, placeholder: { type: String, optional: true }, value: { type: String, optional: true }

    };

    setup() {
        useInputField({ getValue: () => this.props.record.data[this.props.name] || "" });

    }
    formatNumber(event) {
        const input = event.target;
        const value = input.value.replace(/\./g, '').replace(/,/g, '');
        const formattedValue = new Intl.NumberFormat('es-AR').format(value || 0);
        input.value = formattedValue;
    }

}

export const myWidget = {
    component: MyWidget,
    displayName: "Widget",
    supportedTypes: ["float"],
    extractProps: ({ attrs }) => ({
        placeholder:
            attrs.placeholder,
        value: attrs.value,

    }),
};

registry.category("fields").add("MyWidget", myWidget);