/** @odoo-module **/

import { FormController } from "@web/views/form/form_controller";
import { FormRenderer } from "@web/views/form/form_renderer";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

// GLOBAL STATE
let models = [];
let auto_save_boolean_all = false;
let auto_save_boolean = false;

// ==============================
//  HELPERS
// ==============================
async function loadPreventConfig(orm) {
    const lines = await orm.searchRead("prevent.model.line", [], ["model"]);
    const confAll = await orm.searchRead("prevent.model", [], ["auto_save_prevent_all"]);
    const conf = await orm.searchRead("prevent.model", [], ["auto_save_prevent"]);

    models = lines.map(r => r.model);
    auto_save_boolean_all = confAll.some(r => r.auto_save_prevent_all);
    auto_save_boolean = conf.some(r => r.auto_save_prevent);
}

function shouldPrevent(model) {
    if (auto_save_boolean_all) return true;
    if (auto_save_boolean && models.includes(model)) return true;
    return false;
}

// ==============================
//  PATCH: FORM CONTROLLER
// ==============================
patch(FormController.prototype, {
    async setup() {
        super.setup(...arguments);
        this.orm = useService("orm");

        await loadPreventConfig(this.orm);

        // Patch autosave dari browser events
        this._disableBrowserAutoSave();
    },

    _disableBrowserAutoSave() {
        // Mencegah auto-save saat reload / close tab
        window.addEventListener("beforeunload", () => {
            if (shouldPrevent(this.model.root.resModel)) {
                console.warn("Disable Browser - beforeUnload");
                this.model.root.discard();
            }
        });

        // Mencegah autosave saat tab tidak aktif / user pindah window
        document.addEventListener("visibilitychange", () => {
            const root = this.model.root;
            if (document.hidden && shouldPrevent(this.model.root.resModel)) {
                console.warn("Disable Browser - visibilityChange");
                return true;
            }
        });
    },

    async beforeLeave() {
        const root = this.model.root;
        if (shouldPrevent(root.resModel)) {
            console.warn("Block beforeLeave");
            root.discard();
            return true;
        }
        return super.beforeLeave();
    },

    async beforeUnload() {
        const root = this.model.root;
        if (shouldPrevent(root.resModel)) {
            console.warn("Block beforeUnload");
            root.discard();
            return true;
        }
        return super.beforeUnload();
    },
});

// ==============================
//  PATCH: FORM RENDERER
// (Odoo autosave sering dipicu dari sini)
// ==============================
patch(FormRenderer.prototype, {
    async onBlur(ev) {
        // Override total → jangan panggil autosave
        ev.stopPropagation();
        
        const root = this.env.model.root;
        if (shouldPrevent(root.resModel)) {
            console.warn("Block onBlur");
            root.discard();
            return;
        }

        // Gunakan default behavior jika autosave tidak dimatikan
        return super.onBlur?.(ev);
    },
});

patch(FormController.prototype, {
    setup() {
        super.setup();
        onMounted(() => {
            const btnNew = document.querySelector('.discard-new');
            const btnEdit = document.querySelector('.discard-edit');
            if (btnNew) {
                btnNew.addEventListener('click', async () => {
                    this.actionService.restore();
                });
            }
            if (btnEdit) {
                btnEdit.addEventListener('click', async () => {
                    const record = this.model.root;

                    // 1. Simpan perubahan field 'state' ke server melalui RPC
                    await record.update({ is_edit: false });
                    // 2. Simpan seluruh record secara permanen
                    const saved = await record.save();
                    if (saved) {
                        this.actionService.restore();
                    }
                });
            }
        });
    }
});

/** @odoo-module **/
import { registry } from "@web/core/registry";

const userMenuRegistry = registry.category("user_menuitems");

// 1. Tambahkan menu kustom Anda (jika belum ada)
userMenuRegistry.add("my_custom_preferences", (env) => {
    return {
        type: "item",
        id: "my_custom_preferences",
        description: "My Preferences",
        callback: () => {
            env.services.action.doAction("general.action_my_preferences");
        },
        sequence: 10,
    };
}, { force: true });

// 2. Fungsi untuk membersihkan menu lainnya
function cleanupUserMenu() {
    const itemsToRemove = [
        "settings",      // Menu Preferences bawaan
        "documentation", // Menu Dokumentasi
        "support",       // Menu Support
        "odoo_account",  // Menu Odoo.com
        "shortcuts",     // Menu Shortcuts
        "debug",         // Menu Debug
    ];

    itemsToRemove.forEach((item) => {
        if (userMenuRegistry.contains(item)) {
            userMenuRegistry.remove(item);
        }
    });
}

// Jalankan pembersihan
cleanupUserMenu();
