# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a collection of **Odoo 17.0** custom modules by Bonoworx that together form a complete ERP system covering Sales, Purchases, Inventory, Accounting, Employee management, and a custom RBAC (Role-Based Access Control) system. Each directory is an independent Odoo module.

## Module Dependency Order

```
disable_autosave  ←─  base
general           ←─  base, disable_autosave
employees         ←─  base, general, disable_autosave
sales             ←─  base, general, employees, disable_autosave, mail
purchases         ←─  base, general, sales, employees, disable_autosave, mail
inventory         ←─  base, general, sales, purchases, disable_autosave
accounting        ←─  base, general, disable_autosave, sales, purchases
user_management   ←─  base, general, disable_autosave
```

When making cross-module changes, respect this dependency chain. `general` is the foundation.

## Commands

```bash
# Start Odoo with modules available
odoo --addons-path=/path/to/mode -d <database> -u <module_name>

# Initialize fresh database
odoo --addons-path=/path/to/mode -d <database> -i general,sales,purchases,inventory,accounting,employees,user_management,disable_autosave
```

No tests, linters, or build scripts. Module upgrades via `-u <module>`.

## Architecture

### Custom RBAC System (general module)

- **`general.menu`** — Defines all menu items with a `menu_id` string code (e.g., `'sales_order'`, `'rfq'`, `'customers'`).
- **`general.custom_users`** — Wraps `res.users` with additional fields (position, image). Creation syncs to `res.users` and `res.partner`.
- **`general.auth`** — Granular menu-level permissions per user: `can_create`, `can_update`, `can_delete`, `can_submit`, `can_send`, `can_confirm`, `can_invoicing`, `can_receive`, `can_billing`, `can_commission`.
- **`res.users`** (extended) — Has `hide_menu_ids`. `_refresh_custom_menu_access()` rebuilds menu visibility on login.
- **`ir.ui.menu`** (extended) — Has `restrict_user_ids`. `_filter_visible_menus()` hides menus from restricted users (admins bypass).

**Permission flow:** Login → `_update_last_login()` → `_refresh_custom_menu_access()` → for each `general.menu`, if no `general.auth` entry, menu is hidden. `NavigationMixin.get_views()` strips `Create` button when `can_create` is False.

### Per-Module Access Mixins

| Module | Mixin | `_name` | Notes |
|--------|-------|---------|-------|
| general | `NavigationMixin` | `navigation.mixin` | Original — provides CRUD permissions, `get_views()`, `action_edit/save/delete/back` |
| sales | `NavigationMixin` | `navigation.mixin` | Identical copy — keep in sync with general |
| employees | `NavigationMixin` | `navigation.mixin` | Identical copy — keep in sync with general |
| purchases | `PurchaseEditMixin` | `purchases.edit.mixin` | Simpler variant |
| inventory | `InventoryAccessMixin` | `inventory.access.mixin` | Enhanced — `user_can_confirm`, operation-type-based menu codes, `skip_inventory_access` |

### Form Header Button Standard

Every form follows a strict header button layout. **Back must always be first (far left).**

**Required invisible fields in every form header:**
```xml
<field name="is_edit" invisible="1"/>
<field name="user_can_update" invisible="1"/>
<field name="user_can_delete" invisible="1"/>
```

**Standard button set (exact order and conditions):**

| # | Button | `invisible` | When visible |
|---|--------|-------------|-------------|
| 1 | **Back** | `is_edit or not id` | Viewing existing record |
| 2 | **Edit** (active) | `not id or is_edit or not user_can_update` | Viewing with permission |
| 3 | **Edit** (disabled) | `not id or is_edit or user_can_update` | Viewing without permission |
| 4 | **Save** | `id and not is_edit` | New record OR editing |
| 5 | **Cancel** (discard-new) | `id` | New record only |
| 6 | **Cancel** (discard-edit) | `not is_edit` | Editing existing |
| 7 | **Delete** (active) | `not id or is_edit or not user_can_delete` | Viewing with permission |
| 8 | **Delete** (disabled) | `not id or is_edit or user_can_delete` | Viewing without permission |

**Layout rules:**
- `.o_control_panel { display: none !important; }` in every form header
- `model_description` span between buttons and statusbar
- All sheet fields: `readonly="not is_edit and id"`
- Action-specific buttons (Post, Confirm, Send) go between Back and `model_description`

### Sales Module

**Flow:** Quotations → (approval) → Sales Orders → Invoices + Deliveries

Key models: `sales.customer`, `sales.products`, `sales.sales_order`, `sales.sales_order_line`, `sales.price_condition`, `sales.payment_terms`, `sales.taxes`, `sales.sales_approval_matrix`, `sales.invoice`, `sales.payment`, `sales.delivery`, plus supporting lookup tables and wizard models.

**Indent Logic** — `info` field on `sales_order_line`:
- `_set_indent_from_availability()` (onchange): always resets `info` to `"Indent"` or `""` based on stock vs demand
- `_refresh_line_indent_flags()` (on save): only clears `"Indent"` when stock becomes sufficient; never overwrites user-edited custom text
- User-edited values preserved on save

### Purchases Module

**Flow:** RFQs → Purchase Orders → Bills + Receipts

Key models: `purchases.vendor`, `purchases.purchase_order`, `purchases.purchase_order_line`, `purchases.bill`, `purchases.bill.line`, `purchases.receipt`, `purchases.receipt.line`, approval matrix and wizard models.

**Procurement** (`sales_procurement.py`): Auto-creates RFQs from SOs for products with insufficient stock. Products without a configured vendor are silently skipped (no UserError).

### Inventory Module

Uses `InventoryAccessMixin`. Models: `inventory.warehouse`, `inventory.location`, `inventory.stock_move`, `inventory.transfer`, `inventory.adjustment`. Auto-creates transfers from PO/SO writes. Transfers validate → stock moves + delivery/receipt documents.

### Accounting Module

**Core models:** `accounting.account.type`, `accounting.account`, `accounting.journal`, `accounting.fiscal.year`, `accounting.period`, `accounting.move`, `accounting.move.line`, `accounting.bank.statement`, `accounting.bank.statement.line`.

**Sales/Purchases integration** (via `_inherit`):
- `sales_invoice_accounting` — `_create_accounting_move()`: Dr AR / Cr Revenue / Cr Tax + Commission lines
- `sales_payment_accounting` — Dr Cash / Cr AR
- `purchases_bill_accounting` — Original expense-based bill move
- `purchases_payment_register_accounting` — Dr AP / Cr Cash

**Report Wizards + SQL Views:** Trial Balance, General Ledger, Aged Receivable, Balance Sheet, Profit And Loss. Reports render as `qweb-html` with PDF printable via Odoo's Print button.

**Chart of Accounts (15 accounts):**
| Code | Name | Type |
|------|------|------|
| 100000 | Cash / Bank | bank |
| 110000 | Accounts Receivable | receivable |
| 113100 | Inventory | current_asset |
| 113200 | Stock Interim Received | current_asset |
| 130000 | Prepayments | prepayment |
| 140000 | Fixed Assets | fixed_asset |
| 141000 | Accumulated Depreciation | fixed_asset |
| 210000 | Tax Payable | tax |
| 220000 | Accounts Payable | payable |
| 300000 | Equity | equity |
| 310000 | Retained Earnings | equity |
| 400000 | Sales Revenue | income |
| 410000 | Service Revenue | income |
| 500000 | Cost of Goods Sold | expense |
| 510000 | Operating Expenses | expense |

**Menu structure:**
```
Accounting
├── Transactions → Journal Entries
├── Banking → Bank Statements
├── Ledger → Trial Balance / General Ledger / Aged Receivable
├── Reporting → Balance Sheet / Profit And Loss
├── Commissions → Commission Plans / Commission Settlements
└── Accounting Configuration → COA / Account Types / Journals / Fiscal Years / Periods
```

### Commission System

**`accounting.commission.plan`** — Master data: `type` (percentage/fixed), `rate`, `based_on` (untaxed/total), `journal_id`, `expense_account_id`, `payable_account_id`.

**`accounting.commission.settlement`** — Per-invoice settlement: auto-created and auto-posted when invoice is posted. Linked to the same `accounting.move` as the invoice.

**Flow:** Invoice posted → `_create_accounting_move()` → commission lines added inline:
```
Dr Commission Expense (plan.expense_account_id or 510000)
    Cr Commission Payable (plan.payable_account_id or 220000)
```
Settlement record auto-created, linked to the move, and marked posted.

### Product Category Account Properties

`product_category_account` (`_inherit='sales.product_category'`) adds three fields:
- `income_account_id` (required) — Revenue account for sales
- `expense_account_id` — Expense/COGS account
- `stock_account_id` — Stock/Inventory account

Validation: if one of expense/stock is filled, the other becomes required.

**Integration points:**
- **Sales Invoice revenue:** per-line account from `product_id.product_category.income_account_id` (fallback: 400000)
- **Purchase Bill:** per-line account from `product_id.product_category.expense_account_id` (fallback: 500000)

### Delivery Accounting (COGS)

`sales_delivery_accounting` (`_inherit='sales.delivery'`):
- `create()` and `write()` detect state transition to `'done'`
- Creates COGS journal entry per delivery line: `Dr expense_account_id / Cr stock_account_id`
- Amount: `delivery_line.quantity × product.price`
- Handles both manual Validate and auto-created (inventory transfer) paths

### Receipt Accounting (Stock Interim)

`purchases_receipt_accounting` (`_inherit='purchases.receipt'`):
- `create()` and `write()` detect state transition to `'received'`
- Creates journal: `Dr stock_account_id / Cr 113200 (Stock Interim Received)`
- Amount: `receipt_line.quantity × product.price`

### Bill Accounting (Interim)

`purchases_bill_accounting_interim` (`_inherit='purchases.bill'`):
- Overrides `_create_accounting_move()` to use interim account
- Journal: `Dr 113200 (Stock Interim Received) / Cr Accounts Payable (220000)`
- Net effect after Receipt + Bill: `Dr Stock / Cr AP` (113200 nets to zero)

### Balance Sheet & Profit And Loss

- **Balance Sheet:** SQL view with Assets (Current/Fixed Asset sub-groups), Liabilities, Equity. Retained Earnings = account 310000 balance + Net Income.
- **Profit And Loss:** SQL view with Revenue / Expenses sections, Net Profit/Loss.
- Both use `qweb-html` report type; Odoo Print button generates PDF.
- Wizards provide date filters (passed via context).

## Key Patterns

### Edit/Save Pattern
`is_edit` Boolean + `action_edit()`/`action_save()`. Fields: `readonly="not is_edit and id"`.

### Sequence-Generated IDs
All master/transaction records use `ir.sequence`. Defined in each module's `data/sequence.xml`.

### Partner Synchronization
`sales.customer` and `purchases.vendor` sync to `res.partner`. Changes propagate; deletion cascades.

### Wizard Confirmation Pattern
Model's `action_<name>()` validates state → opens `TransientModel` wizard → `action_<name>_confirm()` calls back to `action_<name>_final()`.

### Context-Based Permission Bypass
`skip_inventory_access`, `skip_auto_inventory_receipt_transfer`, `skip_auto_inventory_delivery_transfer`, `skip_purchase_order_create_auth_check`.

### SQL View Report Models (`_auto = False`)
`init()` does `CREATE OR REPLACE VIEW`. All fields `readonly=True`. Read-only in security ACLs.

### Accounting Auto-Posting Pattern
`_inherit` on source models, override `action_post()` to call `super()` then `_create_accounting_move()`. Smart button links to the move.

### Create/Write State Detection Pattern
For auto-created records (delivery, receipt) that bypass action methods, use `create()` + `write()` to detect state transitions. Check `vals.get('state')` in write and check initial state in create. This handles both manual and programmatic paths.
