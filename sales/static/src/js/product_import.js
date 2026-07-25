/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onMounted } from "@odoo/owl";

export class ProductImportProgress extends Component {
    static template = "sales.ProductImportProgress";

    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            status: "running",
            total: 0,
            current: 0,
            created: 0,
            updated: 0,
            skipped: 0,
            lastError: "",
            wizardId: 0,
        });
        onMounted(() => this._start());
    }

    get progressPct() {
        return this.state.total ? Math.round((this.state.current / this.state.total) * 100) : 0;
    }

    async _start() {
        const ctx = this.props.action.context || {};
        this.state.wizardId = ctx.default_wizard_id || 0;
        this.state.total = ctx.default_total_rows || 0;
        this.state.current = ctx.default_current_row || 0;

        if (!this.state.wizardId) {
            this.state.status = "error";
            this.state.lastError = "No wizard ID found.";
            return;
        }

        while (this.state.current < this.state.total && this.state.status === "running") {
            try {
                await this.rpc("/web/dataset/call_kw", {
                    model: "sales.product.import",
                    method: "action_import_batch",
                    args: [[this.state.wizardId]],
                    kwargs: {},
                });

                const records = await this.rpc("/web/dataset/call_kw", {
                    model: "sales.product.import",
                    method: "read",
                    args: [[this.state.wizardId], ["current_row", "created_count", "updated_count", "skipped_count", "last_error", "state"]],
                    kwargs: {},
                });

                if (records && records.length) {
                    const w = records[0];
                    this.state.current = w.current_row || 0;
                    this.state.created = w.created_count || 0;
                    this.state.updated = w.updated_count || 0;
                    this.state.skipped = w.skipped_count || 0;
                    this.state.lastError = w.last_error || "";

                    if (w.state === "done") {
                        this.state.status = "done";
                        return;
                    }
                } else {
                    this.state.status = "error";
                    this.state.lastError = "Wizard record not found.";
                    return;
                }

                await new Promise((r) => setTimeout(r, 50));
            } catch (e) {
                this.state.status = "error";
                this.state.lastError = e.message || String(e);
                return;
            }
        }

        this.state.status = "done";
    }

    onClose() {
        window.location.href = '/web';
    }
}

registry.category("actions").add("product_import_progress", ProductImportProgress);
