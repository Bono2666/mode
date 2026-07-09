/** @odoo-module **/

import { Many2OneField } from "@web/views/fields/many2one/many2one_field";

/**
 * Global default: all Many2one dropdowns get no_open=true and no_create=true
 * unless a view explicitly sets the option to false.
 *
 * This is the client-side fallback. The primary enforcement is server-side
 * via inject_m2o_no_open_create() called from NavigationMixin.get_views().
 *
 * To opt out per-field, set the option explicitly in the view:
 *   <field name="partner_id" options="{'no_open': False, 'no_create': False}"/>
 */

const _origSetup = Many2OneField.prototype.setup;

Many2OneField.prototype.setup = function () {
    // Pre-setup: inject defaults into options so the parent setup processes them
    const rawOpts = this.props.options;
    const merged = Object.assign({}, rawOpts || {});
    if (!('no_open' in merged)) {
        merged.no_open = true;
    }
    if (!('no_create' in merged)) {
        merged.no_create = true;
    }
    this.props.options = merged;
    return _origSetup.call(this);
};
