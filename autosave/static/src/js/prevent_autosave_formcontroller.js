/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

let models;
let auto_save_boolean_all;
let auto_save_boolean;


patch(FormController.prototype, {
    async setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        await this.getFormData();
    },

    async getFormData (){
        models = await this.orm.searchRead('prevent.model.line', [], ['model']);
        auto_save_boolean_all = await this.orm.searchRead('prevent.model', [], ['auto_save_prevent_all']);
        auto_save_boolean = await this.orm.searchRead('prevent.model', [], ['auto_save_prevent']);
    },

    _handleFormSave(root) {
        var model_lst = models.map(dict => dict.model);
        var boolean_all_lst = auto_save_boolean_all.map(dict => dict.auto_save_prevent_all);
        var boolean_lst = auto_save_boolean.map(dict => dict.auto_save_prevent);
        if (boolean_all_lst.includes(true)) {
            root.discard();
            return true;
        }
        else if (model_lst.includes(root.resModel) && boolean_lst.includes(true)) {
            root.discard();
            return true;
        }
        else {
            root.urgentSave();
            return true;
        }
    },

    async beforeLeave(){
        var root = this.model.root;
        if (root.isDirty) {
            return this._handleFormSave(root);
        }
    },

    async beforeUnload(){
        var root = this.model.root;
        if (root.isDirty) {
            return this._handleFormSave(root);
        }
    },

});

// document.addEventListener('mouseleave', function(event) {
//     if (event.clientY <= 0) {  // Check if mouse is leaving through the top
//         var save_hide = document.querySelector('.o_form_status_indicator_buttons.d-flex.invisible');
//         if (document.querySelector('.o_form_status_indicator_buttons.d-flex')) {
//             if (save_hide === null) {
//                 alert("Saving or Discarding changes before leaving the page.");
//             }
//         }
//     }
// });

// window.addEventListener('blur', function() {
//     var save_hide = document.querySelector('.o_form_status_indicator_buttons.d-flex.invisible');
//     if (document.querySelector('.o_form_status_indicator_buttons.d-flex')) {
//         if (save_hide === null) {
//             alert("Saving or Discarding changes before leaving the page.");
//         }
//     }
// });