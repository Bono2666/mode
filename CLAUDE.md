# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of **Odoo 17.0** custom modules by Bonoworx that together form a complete ERP system covering Sales, Purchases, Inventory, Employee management, and a custom RBAC (Role-Based Access Control) system. Each directory is an independent Odoo module.

## Module Dependency Order

```
disable_autosave  ←─  base
general           ←─  base, disable_autosave
user_management   ←─  base, general, disable_autosave
employees         ←─  base, general, disable_autosave
sales             ←─  base, general, employees, disable_autosave, mail
purchases         ←─  base, general, sales, employees, disable_autosave, mail
inventory         ←─  base, general, sales, purchases, disable_autosave
accounting        ←─  base, general, disable_autosave, sales, purchases
```

When making cross-module changes, respect this dependency chain. `general` is the foundation that all other modules depend on.

## Commands

This is an Odoo addons directory. It is deployed by placing it in an Odoo instance's `addons` path and installing modules through the Odoo Apps menu or CLI.

```bash
# Start Odoo with these modules available (add to addons path)
odoo --addons-path=/path/to/mode -d <database> -u <module_name>

# Upgrade a specific module (e.g., after schema changes)
odoo --addons-path=/path/to/mode -d <database> -u sales --stop-after-init

# Initialize a fresh database with all modules
odoo --addons-path=/path/to/mode -d <database> -i general,sales,purchases,inventory,employees,user_management,disable_autosave
```

There are no tests, linters, or build scripts in this repository. Module upgrades happen via `-u <module>`.

## Architecture

### Custom RBAC System (general module)

The entire application uses a custom permission layer built on top of Odoo's native access control:

- **`general.menu`** — Defines all menu items with a `menu_id` string code (e.g., `'sales_order'`, `'purchase_order'`, `'rfq'`, `'customers'`, `'products'`).
- **`general.custom_users`** — Wraps `res.users` with additional fields (position, image). Creation and deletion here synchronizes to `res.users` and `res.partner`. When a custom user is created, a corresponding `res.users` record is auto-created and linked.
- **`general.auth`** — Stores granular, menu-level permissions per user: `can_create`, `can_update`, `can_delete`, `can_submit`, `can_send`, `can_confirm`, `can_invoicing`, `can_receive`, `can_billing`. Has a uniqueness constraint on `(custom_user_id, menu_id)`.
- **`res.users`** (extended) — Has `hide_menu_ids` (menus restricted from the user). The `_refresh_custom_menu_access()` method rebuilds menu visibility based on `general.auth` entries. Called automatically on login via `_update_last_login()`.
- **`ir.ui.menu`** (extended) — Has `restrict_user_ids`. `_filter_visible_menus()` hides menus from restricted users (admins bypass this).

**How permissions flow:** User logs in → `_update_last_login()` calls `_refresh_custom_menu_access()` → for each `general.menu`, if the user has no `general.auth` entry, that Odoo menu is hidden via `restrict_user_ids`. Additionally, `NavigationMixin.get_views()` manipulates view XML to remove the "Create" button when the user lacks `can_create`.

### Identical NavigationMixin (code duplication — be aware)

`general/models/models.py`, `sales/models/models.py`, and `employees/models/models.py` each define an identical `navigation.mixin` abstract model. These are **separate models** despite having the same `_name`. Each module's models inherit from its own module's version. If you change one, you must replicate the change in all three files. The purchases module uses its own simpler `purchases.edit.mixin` instead, and inventory uses `inventory.access.mixin`.

### Sales Module (`sales`)

**Flow:** Quotations → (approval) → Sales Orders → Invoices + Deliveries

Key models:

- `sales.customer` — Customers synced to `res.partner`. Has ship-to addresses, payment terms, price conditions. Deletion cascades to partner.
- `sales.products` — Products with stock tracking, sales/purchase flags, customer tax, reserved quantity computed from open SOs.
- `sales.sales_order` — Dual role: Quotations (state: draft→wait_approval→approved→sent→sale) and Sales Orders (state: sale_draft→wait_approval→approved→sale). Uses `is_quotation` boolean to distinguish. Inherits `mail.thread` for activity tracking.
- `sales.sales_order_line` — Order lines with price condition auto-application (based on customer category/type and product category/specific product), stock reservation indicator ("Indent" tag), delivery tracking.
- `sales.price_condition` — Tiered pricing: can apply to all/category/specific products, all/category/specific customers. Both fixed price and discount modes. Prioritized by specificity (more specific = higher priority = lower priority number). Synced to customers on create/update.
- `sales.payment_terms` — Payment term templates with installment details and early payment discounts.
- `sales.sales_approval_matrix` — Multi-step approval chain. Each row defines an approver (linked to `general.custom_users`), a minimum amount threshold, and which actions they can perform (approve, revise, return, reject). Approval logs track state per step.
- `sales.invoice` — Custom invoicing (separate from Odoo's native `account.move`). Supports regular invoices and down payments (percentage or fixed).
- `sales.delivery` — Delivery orders linked to sales orders.
- Multiple wizard models (`sales.approve.wizard`, `sales.reject.wizard`, `sales.return.wizard`, `sales.revise.wizard`) for approval workflow interactions.

**Approval flow:** On order line change → `_check_approval_requirement()` checks if total exceeds threshold or discount exceeds base → creates `sales_approval_log` entries for each matrix row with `min_amount < total_amount` → user calls `action_submit_for_approval()` → state becomes `wait_approval` → each approver in sequence approves/revises/returns/rejects → when all approved, state becomes `approved`.

**Invoice flow:** SO state must be `sale` → `action_create_invoice_simple()` opens wizard → creates `sales.invoice` with lines from SO (or down payment calculation) → invoice goes through draft → posted lifecycle.

### Purchases Module (`purchases`)

**Flow:** RFQs → (optional approval) → Purchase Orders → Bills + Receipts

Key models:

- `purchases.vendor` — Vendors synced to `res.partner` with `is_company=True` and `supplier_rank=1`.
- `purchases.purchase_order` — Dual role: RFQs (state: draft→sent) and Purchase Orders (state: draft→purchase→wait_approval→approved). Uses `entry_menu_code` to track which menu the record was created from (`'rfq'` vs `'purchase_order'`). The `get_views()` method handles different permission checks for RFQ vs PO views. Inherits `mail.thread`.
- `purchases.purchase_order_line` — Lines with tax, received quantity tracking, and `qty_to_receive` computed field. `init()` drops a stale FK constraint (migration cleanup).
- `purchases.purchase_approval_matrix` — Same pattern as sales approval matrix. Threshold-based with multi-step sequence.
- `purchases.bill` — Vendor bills with payment tracking and `purchases.payment.register` wizard. Bills are created from POs via `_prepare_bill_vals()`.
- `purchases.receipt` — Goods receipt with stock update on validation. Receipt lines track ordered vs received quantities.
- `purchases.receipt.line` — Links to PO lines, auto-populates from `purchase_order_line_id`.

**RFQ/PO lifecycle:** Created as RFQ (draft) → `action_submit_rfq()` → sent → `action_confirm_order()` → purchase → if approval needed: `action_submit_for_approval()` → wait_approval → approvals process → approved. The `is_sent` flag is set permanently when email is sent.

### Inventory Module (`inventory`)

Key models:

- `inventory.warehouse` — Physical warehouses with locations.
- `inventory.location` — Stock locations with types (internal, supplier, customer, inventory adjustment, transit).
- `inventory.stock_move` — Individual stock movements. `action_done()` applies stock changes to `sales.products.stock`. Tracks origin document/model for traceability.
- `inventory.transfer` — Multi-line transfers (receipt, delivery, internal transfer). On validation, creates individual stock moves and auto-creates `purchases.receipt` or `sales.delivery` records. Links to SO/PO via `sales_order_id`/`purchase_order_id`.
- `inventory.adjustment` — Inventory count adjustments. Compares counted vs current quantity, creates stock moves for differences.

**Auto-creation of inventory transfers:** When a `purchases.purchase_order` enters `to_receive` status, `_ensure_inventory_receipt_transfer()` auto-creates a draft inventory transfer from supplier location to stock location. Similarly, when a `sales.sales_order` enters `sale` state, `_ensure_inventory_delivery_transfer()` auto-creates a delivery transfer from stock to customer location. Both are hooks via `write()` overrides.

### Procurement (purchases/models/sales_procurement.py)

When a Sales Order is created or updated, `_sync_procurement_rfq()` on `sales.sales_order` calculates stock shortages per product and automatically creates or updates RFQs with the vendor assigned to each product (`sales.products.vendor_id`, added by `SalesProductsVendor`). Products without a configured vendor raise a `UserError`. The system links SOs to RFQs via `purchases_purchase_order_sales_order_rel` (M2M).

### Employee Module (`employees`)

Simple module: `employees.employees` model with employee ID (auto-sequenced), name, position (→ `general.position`), department (→ `general.department`), and sales code.

### Disable Autosave (`disable_autosave`)

Technical module that disables Odoo's auto-save via JavaScript (`static/src/js/disable_autosave.js`) and CSS (`static/src/css/disable_autosave.css`). Depended on by all other modules.

### User Management (`user_management`)

Stub module — its model file is entirely commented out. The `security/ir.model.access.csv` is also commented out in the manifest. Exists as a placeholder.

## Key Patterns

### Edit/Save Pattern

Most models use an `is_edit` Boolean field + `action_edit()`/`action_save()` methods. Views conditionally render editable fields based on `is_edit`. `action_edit` sets it to True; `action_save` sets it to False and reloads the form.

### Sequence-Generated IDs

All master/transaction records use `ir.sequence` for auto-generated codes (e.g., `sales.sales_code`, `purchases.po_code`, `inventory.move_number`). Sequences are defined in each module's `data/sequence.xml`.

### Partner Synchronization

Both `sales.customer` and `purchases.vendor` create and sync records to `res.partner`. Changes to name, email, phone, address, image are propagated to the linked partner. Deletion cascades.

### Wizard Confirmation Pattern

Approval actions (approve, reject, return, revise) follow an identical pattern: the model's `action_<name>()` method validates state and opens a `TransientModel` wizard; the wizard's `action_<name>_confirm()` calls back to the model's `action_<name>_final()` with context-carried data.

### Context-Based Permission Bypass

System-generated records (inventory transfers created from SO/PO, receipt stock moves) use context keys like `skip_inventory_access`, `skip_auto_inventory_receipt_transfer`, `skip_purchase_order_create_auth_check` to bypass permission checks that would otherwise block automated operations.
