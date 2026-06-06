/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component } from "@odoo/owl";

export class PurchaseBasedOnSoField extends Component {
    static template = "purchases.BasedOnSoField";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get links() {
        const value = this.props.record.data[this.props.name];
        return Array.isArray(value) ? value : [];
    }

    async onClickSo(soId, ev) {
        ev.preventDefault();
        const poId = this.props.record.resId;
        if (!poId || !soId) {
            return;
        }
        const action = await this.orm.call(
            "purchases.purchase_order",
            "action_open_sales_order",
            [[poId]],
            { context: { open_sales_order_id: soId } }
        );
        if (action) {
            await this.action.doAction(action);
        }
    }
}

export const purchaseBasedOnSoField = {
    component: PurchaseBasedOnSoField,
    supportedTypes: ["json"],
};

registry.category("fields").add("purchase_based_on_so", purchaseBasedOnSoField);
