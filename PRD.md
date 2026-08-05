# PRD.md

This file provides guidance to Agents when working with code in this repository.

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

Module upgrades via `-u <module>`. E2E tests via Playwright + Pytest (see Testing section).

## Architecture

### Custom RBAC System (general module)

#### Data Models

- **`general.menu`** — Defines all menu items with a `menu_id` string code (e.g., `'sales_order'`, `'rfq'`, `'customers'`). Also has `menu_name` (display name), `parent_menu` (parent slug), `is_parent` (boolean), and **`ir_ui_menu_id`** (Many2one to `ir.ui.menu`) for direct linking.
- **`general.custom_users`** — Wraps `res.users` with additional fields (position, image). Creation syncs to `res.users` and `res.partner`.
- **`general.auth`** — Granular menu-level permissions per user: `can_create`, `can_update`, `can_delete`, `can_submit`, `can_send`, `can_confirm`, `can_invoicing`, `can_receive`, `can_billing`, `can_commission`. Each record links a `general.custom_users` to a `general.menu`.
- **`res.users`** (extended) — Has `hide_menu_ids`. `_refresh_custom_menu_access()` rebuilds menu visibility on login.
- **`ir.ui.menu`** (extended) — Has `restrict_user_ids` (Many2many to `res.users`). Users in this list cannot see the menu.

#### The `ir_ui_menu_id` Field (Critical)

**`general.menu.ir_ui_menu_id`** is a Many2one to `ir.ui.menu` that provides a **direct, precise link** between the custom menu definition and the Odoo menu record. This field is essential for correct restriction matching.

**Why it exists:** The original code used `ir.ui.menu.name = general_menu.menu_name` for matching. This is **unsafe** because multiple `ir.ui.menu` records can share the same name (e.g., "Configuration" exists at id=71 under Home and id=51 under Inventory). Name-based matching causes **over-restriction** — restricting menus the user should see.

**Rule:** When adding new menus to `general.menu`, always set `ir_ui_menu_id` to the exact `ir.ui.menu` record. If no match exists, leave it NULL (the menu will be skipped during restriction, which is safer than over-restricting).

#### Login Permission Flow

```
User login
  → _update_last_login()
    → _refresh_custom_menu_access()
      → Step 1: Clear ALL existing restrict_user_ids for this user
      → Step 2: Delete auto-generated parent auth entries
      → Step 3: Compute menu access from general.auth entries
        → Find direct auth entries for the user
        → Auto-create parent auth entries (folders needed to reach allowed menus)
      → Step 4: For each general.menu NOT in the user's auth list:
        → If ir_ui_menu_id is set: restrict that specific ir.ui.menu
        → If ir_ui_menu_id is NULL: skip (no restriction applied)
      → Step 5: Clear registry cache (ormcache_context + ormcache)
```

**Key behaviors:**
- Admin users (`base.group_system`) bypass all restrictions — `_get_restricted_menu_ids()` returns empty set
- `_refresh_custom_menu_access` runs on EVERY login, overwriting any manual DB changes to `restrict_user_ids`
- The `restrict_user_ids` field on `ir.ui.menu` is the **single source of truth** for menu visibility, but it's auto-computed from `general.auth` + `general.menu`
- Every `general.menu` entry MUST have a corresponding `general.auth` entry for each user who should see it. If missing, the menu is restricted.

#### Menu Visibility in the Odoo Webclient

Odoo 17's top navigation bar has three layers:

| Layer | Source | Example |
|-------|--------|---------|
| **Apps dropdown** (hamburger icon) | `root.children` from `load_menus` — root-level menus only (`parent_id IS NULL`) | Home, Discuss |
| **App Brand** | `currentApp.name` — the currently selected app | "Home" |
| **Section tabs** | `currentApp.childrenTree` — children of the current app rendered as dropdowns | Configuration ▼, Purchases ▼ |

**For user 7 (purchases@gmail.com):**
- Apps dropdown: Home (70), Discuss (80) — root-level menus
- When Home is selected: sections = Configuration (71), Purchases (136)
- Configuration dropdown: Invoicing (116) → Payment Terms (124); Product (117) → Product Categories (130), Unit of Measures (132)
- Purchases dropdown: Orders (137) → RfQ (138), PO (139), Vendors (140); Products (143)

#### Menu Pruning (load_menus override)

The `load_menus()` override on `ir.ui.menu` prunes restricted menus from the menu tree returned by Odoo's base `load_menus()`. It does NOT promote menus to root level — children stay as children, appearing as section tabs under their parent.

**Algorithm:**
1. Call `super().load_menus(debug)` to get the full menu tree (base Odoo handles `_visible_menu_ids` / groups filtering)
2. `copy.deepcopy(result)` to avoid corrupting the `ormcache_context` cached result
3. Get restricted menu IDs via `_get_restricted_menu_ids()` (direct DB search, no cache)
4. Expand restricted IDs to include ALL descendants (BFS via `children_map`)
5. Remove restricted menus from the result dict
6. Clean up children lists (remove references to deleted menus)

**Files:** `general/models/models.py` — class `IrUiMenu`

#### Name-Based Matching Bug Fix

**Problem:** `_refresh_custom_menu_access` originally searched `ir.ui.menu` by `name = menu.menu_name`. Multiple menus share names (e.g., "Configuration", "Products", "Inventory"), causing one `general.menu` entry to restrict multiple unrelated `ir.ui.menu` records.

**Fix:** Added `ir_ui_menu_id` field to `general.menu` for direct linking. The restriction logic now uses `menu.ir_ui_menu_id` when available, falling back to skip (no restriction) when NULL.

**When adding new menus:** Always verify `ir_ui_menu_id` is set correctly. Check for duplicate names in `ir.ui.menu`:
```sql
SELECT name, COUNT(*) FROM ir_ui_menu GROUP BY name HAVING COUNT(*) > 1;
```

### Per-Module Access Mixins

| Module    | Mixin                  | `_name`                  | Notes                                                                                                                |
| --------- | ---------------------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------- |
| general   | `NavigationMixin`      | `navigation.mixin`       | Original — CRUD permissions, `get_views()`, `action_edit/save/delete/back`, no_open/no_create injection              |
| sales     | `NavigationMixin`      | `navigation.mixin`       | Identical copy — keep in sync with general, includes own `_inject_m2o_no_open_create`                                |
| employees | `NavigationMixin`      | `navigation.mixin`       | Identical copy — keep in sync with general, includes own `_inject_m2o_no_open_create`                                |
| purchases | `PurchaseEditMixin`    | `purchases.edit.mixin`   | Simpler variant; `bill` and `receipt` models also override `get_views()` with injection                              |
| inventory | `InventoryAccessMixin` | `inventory.access.mixin` | Enhanced — `user_can_confirm`, operation-type-based menu codes, `skip_inventory_access`, no_open/no_create injection |

### Form Header Button Standard

Every form follows a strict header button layout. **Back must always be first (far left).**

**Required invisible fields in every form header:**

```xml
<field name="is_edit" invisible="1"/>
<field name="user_can_update" invisible="1"/>
<field name="user_can_delete" invisible="1"/>
```

**Standard button set (exact order and conditions):**

| #   | Button                    | `invisible`                                | When visible               |
| --- | ------------------------- | ------------------------------------------ | -------------------------- |
| 1   | **Back**                  | `is_edit or not id`                        | Viewing existing record    |
| 2   | **Edit** (active)         | `not id or is_edit or not user_can_update` | Viewing with permission    |
| 3   | **Edit** (disabled)       | `not id or is_edit or user_can_update`     | Viewing without permission |
| 4   | **Save**                  | `id and not is_edit`                       | New record OR editing      |
| 5   | **Cancel** (discard-new)  | `id`                                       | New record only            |
| 6   | **Cancel** (discard-edit) | `not is_edit`                              | Editing existing           |
| 7   | **Delete** (active)       | `not id or is_edit or not user_can_delete` | Viewing with permission    |
| 8   | **Delete** (disabled)     | `not id or is_edit or user_can_delete`     | Viewing without permission |

**Layout rules:**

- `.o_control_panel { display: none !important; }` in every form header
- `model_description` span between buttons and statusbar
- All sheet fields: `readonly="not is_edit and id"`
- Action-specific buttons (Post, Confirm, Send) go between Back and `model_description`

### Sales Module

**Flow:** Quotations → (approval) → Sales Orders → Invoices + Deliveries

Key models: `sales.customer`, `sales.products`, `sales.sales_order`, `sales.sales_order_line`, `sales.price_condition`, `sales.payment_terms`, `sales.taxes`, `sales.sales_approval_matrix`, `sales.invoice`, `sales.payment`, `sales.delivery`, `sales.pricing_margin_config`, plus supporting lookup tables and wizard models.

**Indent Logic** — `info` field on `sales_order_line`:

- `_set_indent_from_availability()` (onchange): always resets `info` to `"Indent"` or `""` based on stock vs demand
- `_refresh_line_indent_flags()` (on save): only clears `"Indent"` when stock becomes sufficient; never overwrites user-edited custom text
- User-edited values preserved on save

**Import Products Wizard** (`sales.product.import`):

- TransientModel for bulk CSV import of products
- Access: Sales → Import Products menu
- CSV columns (10 required): Part No., Substitution Parts Number, Parts Name, Lead Times, Stock JPN, YEN, Weight, Remarks, Product Availability, Product Category
- Flow: Upload CSV → Parse & validate → Batch import (500 rows/batch) → Progress UI → Done
- Auto-creates missing product categories
- Updates existing products (matched by `product_id`)
- Exchange rate conversion: `price_idr = price_yen × exchange_rate`
- Encoding detection: UTF-8, CP932, Shift-JIS, EUC-JP, Latin-1
- Delimiter auto-detection: comma, semicolon, tab

**Pricing Margin Configuration** (`sales.pricing_margin_config`):

- Singleton model — only one config record allowed; `create()` updates existing record instead of creating new
- Access: Configuration → Pricing Margin menu
- Fields: `name`, `reseller_margin` (Float, %), `sales_margin` (Float, %)
- Used by `sales.products` to auto-compute selling prices from base `price`

**Product Price Computation** (`sales.products`):

- `base_price` (Sales Price) — computed from `price × (1 + sales_margin / 100)`, auto-updates when `price` changes
- `reseller_price` — computed from `price × (1 + reseller_margin / 100)`, auto-updates when `price` changes
- Both fields are readonly (computed, no manual override)
- Compute methods read margin from latest `sales.pricing_margin_config` record (`order='id desc'`)
- `base_price` is used as `unit_price` in sales order lines and for tax string display

**Product Price Hierarchy:**

| Field | Tipe | Keterangan | Kapan Dipakai |
|---|---|---|---|
| `price` | Manual | **Harga Pokok (Cost Price)** — harga beli/modal produk | COGS journal entry (`delivery_line.quantity × product.price`), Purchase order unit_price |
| `base_price` | Computed | **Harga Jual ke End User** — `price × (1 + sales_margin / 100)` | Sales Order unit_price (default) |
| `reseller_price` | Computed | **Harga ke Reseller** — `price × (1 + reseller_margin / 100)` | Harga untuk channel reseller |

**Prinsip:** `price` selalu merepresentasikan harga pokok/modal. Margin dihitung dari `price`, bukan sebaliknya. Semua jurnal akuntansi (COGS, Receipt Stock) menggunakan `price` sebagai dasar perhitungan biaya.

**Product Form Conditional Visibility:**

- When `sales_ok = False` (product is not for sale), the following fields are hidden:
  - `reseller_price` (Reseller Price)
  - `base_price` + label + currency + tax_string (Sales Price)
  - `customer_tax` (Customer Tax)
- `remarks` field uses `colspan="2"` to span full width of the form
- Implemented via `invisible="not sales_ok"` on field, label, and div elements
- Applied to both Sales and Purchases product forms

**Sales Order States:**

| State | Description | Action di state ini |
|---|---|---|
| `draft` | Quotation baru | Edit, Delete, Send by Email, Submit for Approval |
| `sale_draft` | Sales Order draft (non-quotation) | Edit, Delete, Confirm |
| `wait_approval` | Menunggu approval | Approve / Revise / Return / Reject |
| `approved` | Sudah disetujui | Edit, Send by Email, Confirm |
| `sent` | Quotation terkirim ke customer | **Confirm** (→ `sale`), Send by Email ulang, Edit |
| `sale` | Sales Order terkunci | Create Invoice, Cancel Order |
| `cancel` | Dibatalkan | Terminal state |

**Send by Email (Quotation):**

- Tombol "Send by Email" hanya tersedia pada state `draft`, `approved`, atau `sent` (untuk resend), dengan syarat user punya permission send dan quotation memiliki minimal satu baris produk.
- Membuka wizard komposisi email dengan pemilih customer (email customer diambil dari master data, bukan alamat partner bebas).
- Template email otomatis mengisi subject (`Quotation {sales_code} - {customer_name}`), body berbahasa Indonesia, dan melampirkan PDF quotation.
- Setelah email terkirim, state berubah dari `draft`/`approved` menjadi `sent` — ditandai permanen bahwa quotation sudah dikirim. Ini terjadi otomatis saat pesan ter-post di chatter.
- **Tidak ada** jurnal akuntansi yang dibuat dari pengiriman email. Pengiriman hanya mencatat chatter message.
- Pada state `sent`, stok produk "di-reserve" (soft reservation via `qty_reserved_sale`): kuantitas dari SO berstatus `sent` ikut dihitung sebagai stok yang sudah dialokasikan.
- Setelah di-`sent`, pengguna dapat **Confirm** untuk mengubah quotation menjadi Sales Order (`state = sale`), yang kemudian membuka tombol Create Invoice.

### Purchases Module

**Flow:** RFQs → Purchase Orders → Bills + Receipts

Key models: `purchases.vendor`, `purchases.purchase_order`, `purchases.purchase_order_line`, `purchases.bill`, `purchases.bill.line`, `purchases.receipt`, `purchases.receipt.line`, `purchases.service_category`, approval matrix and wizard models.

**Service Purchase (order_type = service):**

- `purchases.purchase_order.order_type` (Goods/Service, default Goods): locked to `draft` state, but can be changed until confirmed; all existing/auto-procurement POs stay Goods.
- Service POs use line-level `service_category_id` (master data `purchases.service_category`: category + expense account) instead of `product_id`; `qty_received`/`qty_to_receive` are irrelevant (no receipt).
- **No "Receive Products" button** for Service POs — `receipt_status` is forced to `no`.
- **Create Bill** is available for Service POs once `state in [purchase, approved]` — Email send (`is_sent`) is **not** required (unlike Goods PO).
- Service bills use a **separate sequence** `SBILL######` and post the journal **`Dr Expense (per service_category) / Cr Accounts Payable`** directly — bypassing Stock Interim entirely. Goods bills keep the interim path unchanged.
- Service categories map to expense accounts (default: `530000 — Sales Support Service Expense`; note: `520000` is reserved by the Assets module for Depreciation Expense).
- `sales_order_id` (single Many2one) is user-writable for Service POs (manual tagging to a Sales Order for profitability reporting); for Goods POs it stays auto-fill-only via Auto-Procurement.

**Approval Process (reference pattern for Accounting):**

- Trigger: On `action_confirm_order`, `_check_approval_requirement()` builds `purchases.purchase_approval_log` records **only when `total_amount` exceeds the matrix `min_amount` threshold**. The PO **state stays `purchase`** — it never auto-advances.
- Submission: `action_submit_for_approval()` requires state `purchase` + `need_approval`; transitions the PO to `wait_approval`.
- Per-user action permissions are computed from the matrix: `user_can_approve`, `user_can_revise`, `user_can_return`, `user_can_reject` (plus `user_can_submit`).
- Actions go through dedicated wizards (`purchases.approve/revise/return/reject.wizard`) with reasons; approval is **sequential** — each log marked `approved` advances to the next pending approver.
- Email notification is sent to the next pending approver on submit and after each action (`_send_approval_notification`).
- When the last pending log is approved, the PO becomes `approved`. `action_reject` moves it to `cancel` with `approval_status='rejected'`.
- Full audit trail lives in `purchases.purchase_approval_log`.

**Procurement** (`sales_procurement.py`): Auto-creates RFQs from SOs for products with insufficient stock. Products without a configured vendor still generate RFQs (vendor field left empty). Vendor is validated on action: `action_submit_rfq()` and `action_confirm_order()` both raise UserError if `vendor_id` is empty. Shortage calculation is vendor-aware: quantities from other SOs are only counted against available stock if those SOs' products share the same vendor. Products without a vendor have no cross-SO stock sharing.

**Purchase Order States:**

| State | Description | Action di state ini |
|---|---|---|
| `draft` | Draft RFQ | Edit, Submit RFQ, Cancel |
| `sent` | RFQ terkirim (belum dikonfirmasi) | Confirm Order, Cancel |
| `purchase` | Purchase Order dikonfirmasi | Send by Email, Receive Products, Create Bill, Submit for Approval, Cancel |
| `wait_approval` | Menunggu approval | Approve / Revise / Return / Reject |
| `approved` | Sudah disetujui | Send by Email, Receive Products, Create Bill, Cancel |
| `cancel` | Dibatalkan | Reset to Draft |

**Send by Email (Purchase Order):**

- Tombol "Send by Email" hanya tersedia pada state `purchase` atau `approved`, dengan syarat: user punya permission send, PO belum menerima barang (belum partial/received), dan tidak dalam proses approval (jika `need_approval`, harus sudah `approved`).
- Flow pengiriman:
  1. Validasi state dan permission `can_send`.
  2. **Generate PDF PO** secara eksplisit (`PO - {po_code}.pdf`) dan lampirkan pada email; PDF lama dengan nama sama dihapus agar tidak duplikat.
  3. Pengirim email di-resolve dari user buyer → user login → email company (fallback berurutan).
  4. Email vendor di-sync ke `res.partner` terkait jika berbeda.
  5. **`is_sent` di-set ke `True` secara permanen** (sebelum wizard email dibuka). State PO **tidak berubah**.
  6. Membuka wizard komposisi email dengan pemilih vendor; template otomatis mengisi subject, body berbahasa Indonesia, dan melampirkan PDF.
- Setelah terkirim, tercatat chatter message di PO.
- **Tidak ada** jurnal akuntansi yang dibuat dari pengiriman email.

**`is_sent` Flag (gate utama setelah PO dikirim):**

- `is_sent` bersifat **permanen dan tidak bisa di-reverse** — menandakan PO sudah pernah dikirim ke vendor.
- Saat `is_sent = True` (dan state `purchase`/`approved`):
  - `bill_status` menjadi `to_bill` → tombol **Create Bill** muncul.
  - `receipt_status` mulai dihitung (`to_receive`/`partial`/`received`) → tombol **Receive Products** muncul.
- Saat `is_sent = False`: `bill_status` dan `receipt_status` keduanya `no`, sehingga tombol Create Bill dan Receive Products tersembunyi.
- Dengan kata lain, PO **harus dikirim lewat email terlebih dahulu** sebelum bisa membuat receipt atau bill.

### Inventory Module

Uses `InventoryAccessMixin`. Models: `inventory.warehouse`, `inventory.location`, `inventory.stock_move`, `inventory.transfer`, `inventory.adjustment`. Auto-creates transfers from PO/SO writes. Transfers validate → stock moves + delivery/receipt documents.

### Accounting Module

**Core models:** `accounting.account.type`, `accounting.account`, `accounting.journal`, `accounting.fiscal.year`, `accounting.period`, `accounting.move`, `accounting.move.line`, `accounting.bank.statement`, `accounting.bank.statement.line`, `accounting.commission.plan`, `accounting.commission.settlement`, `accounting.petty.cash`, `accounting.petty.cash.category`, `accounting.petty.cash.expense`, `accounting.petty.cash.topup`, `accounting.petty.cash.transfer`, `accounting.petty.cash.settlement`.

**Sales/Purchases integration** (via `_inherit`):

- `sales_invoice_accounting` — `_create_accounting_move()`: Dr AR / Cr Revenue / Cr Tax + Commission lines
- `sales_payment_accounting` — Dr Cash / Cr AR
- `purchases_bill_accounting` — Original expense-based bill move
- `purchases_payment_register_accounting` — Dr AP / Cr Cash

**Approval Process (matches Purchases):** Accounting documents that need approval (petty cash expense, top-up, transfer, settlement) reuse the exact Purchases approval pattern rather than the old Sales-style authoring. Details:

- Shared `accounting.approval.mixin` provides `approval_log_ids`, `need_approval`, `approval_status`, `current_approver(_name)`, and the computed per-user flags `user_can_approve/revise/return/reject` (+ `user_can_submit`).
- The approval chain is defined in `accounting.approval.matrix` (per `document_type`) and builds `accounting.approval.log` records. Entries that need approval submit from `draft` and transition through `wait_approval` → `approved` before posting.
- Approve / Revise / Return / Reject run through `accounting.approval.wizard` (reason prompts), mirroring the Purchases wizard flow. Approval is sequential and email notification is sent to the next pending approver.
- Full audit trail lives in `accounting.approval.log`, linked back to each document.

**Report Wizards + SQL Views:** Trial Balance, General Ledger, Aged Receivable, Balance Sheet, Profit And Loss. Reports render as `qweb-html` with PDF printable via Odoo's Print button.

**Chart of Accounts (18 accounts):**
| Code | Name | Type |
|------|------|------|
| 100000 | Cash / Bank | bank |
| 100500 | Petty Cash - General | cash |
| 110000 | Accounts Receivable | receivable |
| 113100 | Inventory | current_asset |
| 113200 | Stock Interim Received | current_asset |
| 120000 | Employee Advances | current_asset |
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
| 530000 | Sales Support Service Expense | expense |

**Menu structure:**

```
Accounting
├── Transactions → Journal Entries
├── Banking → Bank Statements
├── Petty Cash → Cash Expenses / Top Ups / Transfers / Settlements
├── Ledger → Trial Balance / General Ledger / Aged Receivable
├── Reporting → Balance Sheet / Profit And Loss / Sales Order Profitability
├── Commissions → Commission Plans / Commission Settlements
└── Accounting Configuration → COA / Account Types / Journals / Fiscal Years / Periods / Petty Cash Funds / Expense Categories
```

### Assets Module

**Flow:** Journal Entry posted → Asset Created (draft) → Confirm → Running → Compute Depreciation (daily cron) → Revaluation (optional) → Disposal

Key models: `assets.model`, `assets.asset`, `assets.depreciation_line`, `assets.revaluation_line`, `assets.disposal_wizard`, `assets.revaluation_wizard`.

**Asset Model** (`assets.model`):

- Template for asset categories (e.g. Vehicles, Office Equipment)
- Fields: `method` (straight_line / declining / declining_then_straight), `method_number`, `method_period`, `method_progress_factor`, `prorata_computation_type`, `account_asset_id`, `account_depreciation_id`, `account_depreciation_expense_id`, `journal_id`
- Auto-fills depreciation settings when creating a new asset

**Fixed Asset** (`assets.asset`):

- State machine: draft → running → paused / close / disposed
- Auto-generated `asset_number` via ir.sequence (`ASSET000001`)
- Key fields: `asset_model_id`, `original_value`, `salvage_value`, `depreciable_value` (computed), `book_value` (computed), `fair_value` (computed from revaluation history), `custodian_id`, `location`, `purchase_line_id`
- `action_confirm()` — moves to running state, calls `_generate_depreciation_lines()`
- `_generate_depreciation_lines()` — supports 3 methods:
  - **Straight Line:** equal depreciation per period
  - **Declining Balance:** diminishing value with configurable factor
  - **Declining then Straight Line:** switches to straight line when beneficial
- `action_pause()` / `action_resume()` — pause/resume depreciation
- `book_value = fair_value - accumulated_depreciation`
- `create()` uses `@api.model_create_multi` decorator for proper list-of-dicts handling

**Depreciation Board** (`assets.depreciation_line`):

- One row per depreciation period in the schedule
- Fields: `sequence`, `depreciation_date`, `depreciation_value`, `accumulated_value` (computed), `remaining_value` (computed), `move_id`
- `action_post_depreciation()` — creates journal entry: Dr Depreciation Expense / Cr Accumulated Depreciation
- Daily cron job (`ir_cron_post_depreciation`) auto-posts all due depreciation lines for running assets

**Revaluation** (`assets.revaluation_line`):

- Records fair value revaluation events on an asset
- Fields: `book_value_before`, `fair_value_after`, `surplus_deficit_value` (computed), `remaining_useful_life`, `note`, `move_id`
- `action_post_revaluation()` — creates journal entries: surplus to equity account, deficit splits between surplus account and impairment loss account

**Disposal Wizard** (`assets.disposal_wizard`):

- TransientModel for full disposal/sale of an asset
- Fields: `sale_price`, `disposal_date`, `gain_loss` (computed from book_value vs sale_price)
- `action_confirm_disposal()` — creates closing entry: Dr Accumulated Depreciation, Dr Cash/Bank (if sold), Cr Asset Account, Dr/Cr Gain/Loss

**Auto-Creation from Journal Entries** (`accounting.move` inherits):

- `accounting_move_asset` class inherits `accounting.move`
- Overrides `action_post()` to call `_create_assets_from_move()` after posting
- `_create_assets_from_move()` scans all **debit lines** in the posted journal entry
- For each line where `debit > 0` AND `account_id.is_asset_account = True`:
  - Creates `assets.asset` in draft state
  - Sets `name` from JE line description
  - Sets `original_value` from JE line debit amount
  - Sets `acquisition_date` from JE date
- **Trigger:** Any journal entry (bills, receipts, manual entries, etc.)
- **No dependency on bill-specific code** — works for any source of journal entries

**`is_asset_account` Field:**

- Added to `accounting.account` model by `assets` module
- Boolean field, default=False
- Visible on COA form view via inherited view (`accounting_account_form_inherit_asset`)
- When a JE is posted with a debit to an account marked `is_asset_account=True`, an asset is auto-created
- To enable: mark the desired account in Chart of Accounts as "Asset Account"

**Chart of Accounts additions:**

| Code | Name | Type |
|------|------|------|
| 114000 | Fixed Assets - Vehicles/Machinery/Equipment | fixed_asset |
| 114900 | Accumulated Depreciation - Fixed Assets | fixed_asset |
| 520000 | Depreciation Expense | expense |
| 420000 | Gain/Loss on Asset Disposal | income |
| 320000 | Revaluation Surplus - Fixed Assets | equity |
| 620000 | Impairment Loss on Fixed Assets | expense |

**Reports:**

- Asset Register — full list with original value, method, book value, status
- Depreciation Schedule — per-asset depreciation board
- Revaluation History — per-asset revaluation audit trail

**Menu structure under Accounting:**

```
Accounting
├── Assets → Assets (list)
├── Accounting Configuration → Asset Models
└── Assets → Depreciation Report
```

**Test Coverage** (Playwright + Pytest — 15 tests, all passing):

| Test Class | Tests | What's Tested |
|------------|-------|---------------|
| `TestAssetModelCRUD` | 3 | Create, edit, delete asset models |
| `TestAssetLifecycle` | 5 | Create, confirm, compute depreciation, pause/resume, dispose |
| `TestAssetDepreciation` | 3 | Line count matches method_number, post line creates JE, straight-line values uniform |
| `TestAssetRevaluation` | 2 | Revalue via wizard (UI), revaluation creates line (RPC) |
| `TestAssetAutoCreation` | 2 | JE posting with asset account debit creates asset, correct original_value |

### Commission System

**`accounting.commission.plan`** — Master data: `type` (percentage/fixed), `rate`, `based_on` (untaxed/total), `journal_id`, `expense_account_id`, `payable_account_id`.

**`accounting.commission.settlement`** — Per-invoice settlement: auto-created and auto-posted when invoice is posted. Linked to the same `accounting.move` as the invoice.

**Flow:** Invoice posted → `_create_accounting_move()` → commission lines added inline:

```
Dr Commission Expense (plan.expense_account_id or 510000)
    Cr Commission Payable (plan.payable_account_id or 220000)
```

Settlement record auto-created, linked to the move, and marked posted.

### Petty Cash System

**Models:** `accounting.petty.cash` (fund), `accounting.petty.cash.category` (expense category), `accounting.petty.cash.expense`, `accounting.petty.cash.topup`, `accounting.petty.cash.transfer`, `accounting.petty.cash.settlement`.

**Default data** (in `sequence.xml`, `noupdate="0"`):

- **Fund:** MAIN — Main Office Cash (journal: Cash Journal, cash account: 100500, expense account: 510000)
- **Categories:** Office Supplies, Transportation, Meals & Entertainment (all → 510000)

**Workflows:**
| Type | States | Journal Entry |
|------|--------|---------------|
| Cash Expense | Draft → (Submit) → Wait Approval → Approved → Posted → Cancelled | `Dr Expense / Cr Petty Cash` |
| Top Up | Draft → (Submit) → Wait Approval → Approved → Posted | `Dr Petty Cash / Cr Bank` |
| Transfer | Draft → (Submit) → Wait Approval → Approved → Posted | `Dr Dest Fund / Cr Source Fund` |
| Settlement | Draft → (Submit) → Wait Approval → Approved → Posted | `Dr Petty Cash / Cr Employee Advance` |

**Integration:** Auto-creates `accounting.move` on Post. Smart button links to the move. Uses `navigation.mixin` for permissions.

**Fund model requires:** `code`, `name`, `journal_id` (cash/bank/general), `default_cash_account_id` (cash/bank account). Balance computed from GL.

**Category model requires:** `name`, `expense_account_id` (expense account).

**Settlement `employee_id`:** Uses `ondelete='restrict'` (required field — cannot null on delete).

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
- Amount: `delivery_line.quantity × product.price` (harga pokok produk)
- Handles both manual Validate and auto-created (inventory transfer) paths

### Receipt Accounting (Stock Interim)

`purchases_receipt_accounting` (`_inherit='purchases.receipt'`):

- `create()` and `write()` detect state transition to `'received'`
- Creates journal: `Dr stock_account_id / Cr 113200 (Stock Interim Received)`
- Amount: `receipt_line.quantity × purchase_order_line.unit_price` (uses PO negotiated price, not product master price)

### Bill Accounting (Interim)

`purchases_bill_accounting_interim` (`_inherit='purchases.bill'`):

- Overrides `_create_accounting_move()` to use interim account
- Journal: `Dr 113200 (Stock Interim Received) / Cr Accounts Payable (220000)`
- Net effect after Receipt + Bill: `Dr Stock / Cr AP` (113200 nets to zero)

### Bill Accounting (Service)

`purchases_bill_accounting_service` (`_inherit='purchases.bill'`):

- Overrides `action_post()` to dispatch on `purchase_order_id.order_type`
- **Service PO:** `_create_service_accounting_move()` — `Dr service_category_id.expense_account_id (530000) / Cr Accounts Payable (220000)` directly, bypassing Stock Interim entirely
- **Goods PO:** unchanged — interim path via `purchases_bill_accounting_interim`
- Mutual exclusion guard: the two hooks are **never** active for the same Bill; `order_type` determines which runs
- Service bills use a **separate sequence `SBILL######`** (6-digit padding, consistent with `BILL`)
- See full PRD: §"Purchases Service Bill — PRD" in the Appendix at end of this file

### Balance Sheet & Profit And Loss

- **Balance Sheet:** SQL view with Assets (Current/Fixed Asset sub-groups), Liabilities, Equity. Retained Earnings = account 310000 balance + Net Income.
- **Profit And Loss:** SQL view with Revenue / Expenses sections, Net Profit/Loss.
- Both use `qweb-html` report type; Odoo Print button generates PDF.
- Wizards provide date filters (passed via context).

### Sales Order Profitability Report

SQL view report model (`_auto = False`) showing per-SO revenue, cost breakdown, and margin.

**Model:** `accounting.sales_profitability_report`

| Field | Type | Source |
|-------|------|--------|
| `sale_order_id` | Many2one → `sales.sales_order` | `so.id` |
| `sale_order_name` | Char | `so.sales_code` |
| `sale_order_date` | Date | `so.create_date` |
| `customer_id` | Many2one → `sales.customer` | `so.customer_id` |
| `total_revenue` | Monetary | Invoice lines with `account_type = 'income'` |
| `cost_cogs` | Monetary | Delivery lines with `account_type = 'expense'` |
| `cost_commission` | Monetary | Invoice expense lines (commission) |
| `cost_supporting` | Monetary | Petty Cash tagged to SO + Purchases Service Bills tagged to SO |
| `total_cost` | Monetary | `cost_cogs + cost_commission + cost_supporting` |
| `margin_amount` | Monetary | `total_revenue - total_cost` |
| `margin_percent` | Float | `(margin_amount / total_revenue) × 100` |

**`cost_supporting` sourcing (v1):**

1. **Petty Cash Expense** — `accounting_petty_cash_expense` where `sales_order_id IS NOT NULL` (manual tagging at input). Field `sales_order_id` added to `accounting.petty.cash.expense` for this purpose.
2. **Purchases Service Bills** — `purchases_bill` where parent `purchase_order.order_type = 'service'` and `po.sales_order_id IS NOT NULL`. Uses `po.sales_order_id` (not the Bill itself).

Filter `am.state = 'posted'` on all accounting moves. `account_type = 'expense'` filters expense lines; `account_type = 'income'` filters revenue lines.

**Wizard:** `accounting.sales_profitability_report.wizard` (TransientModel)
- Fields: `date_from`, `date_to`, `customer_id` (optional), `sale_order_ids` (optional)
- Opens the report list view with domain filter passed via context.

**Menu:** `Accounting → Reporting → Sales Order Profitability`
- RBAC entry in `general.menu` with proper `ir_ui_menu_id`; read-only ACL.

**Drill-down:** Click SO row → opens form view of the Sales Order.

**PDF:** `qweb-html` report, Odoo Print button.

See full PRD: §"Sales Order Profitability Report — PRD" in the Appendix at end of this file.

## Testing

**Framework:** Playwright + Pytest (Python)
**Location:** `tests/` directory at project root

### Running Tests

```bash
cd tests
pip install -r requirements.txt
playwright install chromium
pytest                                          # All tests
pytest -m asset                                 # Asset management tests only
pytest -m happy_path                            # Import Products happy path
pytest -m error_handling                        # Import Products error handling
pytest -v --tb=short                            # Verbose output
pytest test_asset_management.py -v              # Asset tests only
pytest test_import_products.py -v               # Import tests only
```

### Test Structure

```
tests/
├── conftest.py                    # Fixtures: login, navigation, form helpers, RPC helpers
├── pytest.ini                     # Pytest config + markers (asset, happy_path, etc.)
├── requirements.txt               # playwright, pytest, pytest-playwright
├── test_asset_management.py       # 15 test cases for Asset Management (all passing)
├── test_import_products.py        # 12 test cases for Import Products
└── fixtures/
    ├── valid_products.csv         # 3 products (happy path)
    ├── bulk_products.csv          # 30 products (bulk/progress test)
    ├── invalid_columns.csv        # < 10 columns (error test)
    ├── empty_file.csv             # Empty file (error test)
    ├── update_product.csv         # Existing product_id (update test)
    ├── mixed_products.csv         # 1 new + 1 existing (mixed test)
    ├── new_category_product.csv   # New category (edge case)
    └── semicolon_delimited.csv    # Semicolon delimiter (edge case)
```

### Test Categories

| Marker           | Tests | Coverage                                      |
|------------------|-------|-----------------------------------------------|
| `asset`          | 15    | Asset model CRUD, lifecycle, depreciation, revaluation, auto-creation |
| `happy_path`     | 3     | Navigate, import valid CSV, bulk              |
| `error_handling` | 3     | No file, wrong columns, empty                 |
| `update`         | 2     | Update existing, mixed import                 |
| `progress_ui`    | 2     | Progress bar, close button                    |
| `edge_cases`     | 2     | New category, semicolon delimiter             |

### Configuration

Environment variables (optional):
- `ODOO_URL` — Odoo instance URL (default: `http://localhost:8017`)
- `ODOO_DB` — Database name (default: `mina`)
- `ODOO_USER` — Login email (default: `trihambono@gmail.com`)
- `ODOO_PASS` — Login password (default: `Tr1-B0n0`)

### Key Implementation Notes

**Import Products:**
- Browser opens non-headless by default for debugging
- Login uses URL-based DB selection: `/web/login?db=<dbname>`
- File input is hidden (`d-none`); `set_input_files()` works on hidden inputs
- Import uses async batch processing; tests wait for `.o_import_done` selector
- Results parsed from `<strong>` elements inside `.o_import_done`

**Asset Management:**
- Odoo 17 `.o_dialog` container has `height=0` — Playwright `.is_visible()` returns false; always use `.modal` selectors for dialog fields
- `navigation.mixin` hides `.o_control_panel` — "New" button invisible; navigate via direct URL: `/web#model=X&action=Y&view_type=form`
- Wizard buttons with `confirm="Are you sure..."` attribute create stacked modals — dismiss via JS `page.evaluate()` clicking Ok buttons directly, not Playwright locators
- `fill_dialog_field()` uses `force=True` on click and conditional popover dismiss (only presses Escape if `.o_popover:visible` detected)
- `create_asset_with_accounts()` uses JSON-RPC (`/web/dataset/call_kw`) with `odoo.csrf_token` for reliable asset creation
- Selection field options are JSON-encoded in HTML (e.g. `&quot;straight_line&quot;` not bare `straight_line`)
- Statusbar widget renders as `button[aria-current="step"]` with `data-value` attribute, not hidden `<input>`
- Form `<input>` elements lack `name` attribute — target parent `<div class="o_field_widget[name="FIELD_NAME"]">` instead
- Many2one autocomplete uses `input.o-autocomplete--input` with dropdown items in `.o-autocomplete .dropdown-item`

### conftest.py Helper Functions

| Helper | Purpose |
|--------|---------|
| `login(page)` | Logs in via URL-based DB selection; waits 8s for session |
| `click_nav_item(page, name)` | Clicks navbar section tab (leaf `<a>` or dropdown `<button>`) |
| `navigate_to_asset_model_new/list(page)` | Direct URL navigation to asset model forms |
| `navigate_to_asset_new/list(page)` | Direct URL navigation to asset forms |
| `navigate_to_journal_entries(page)` | Sidebar navigation to journal entries |
| `navigate_to_import_products(page)` | Sidebar navigation to import products wizard |
| `fill_field(page, field_name, value)` | Fills standard Odoo 17 widget field (div[name] > input pattern) |
| `fill_many2one_field(page, field_name, text)` | Types into many2one autocomplete + ArrowDown/Enter fallback |
| `fill_dialog_field(page, field_name, value)` | Fills field inside dialog/wizard (`.modal` selectors, `force=True`) |
| `select_field(page, field_name, value)` | Selects option from Selection widget (JSON-encoded value matching) |
| `click_header_button(page, text)` | Clicks navigation.mixin header button (excludes statusbar radio buttons) |
| `click_dialog_confirm(page)` | Clicks wizard confirm button + handles "Are you sure?" popup |
| `get_state_text(page)` | Reads statusbar widget state from `button[aria-current="step"]` |
| `open_first_record(page)` | Clicks first row in list/tree view |
| `click_save_button(page)` | Clicks Save button in form header |
| `click_edit_button(page)` | Clicks Edit button in form header |
| `create_asset_with_accounts(page, name, confirm)` | Creates asset via JSON-RPC with all required accounts; navigates to it |
| `upload_csv_and_import(page, csv_path)` | Uploads CSV file and clicks Import |
| `wait_for_import_complete(page)` | Waits for `.o_import_done` or `.o_import_error` selector |
| `get_import_results(page)` | Parses Created/Updated/Skipped counts from import results |
| `close_import_dialog(page)` | Closes import dialog via Close or Cancel button |

## Key Patterns

### Edit/Save Pattern

`is_edit` Boolean + `action_edit()`/`action_save()`. Fields: `readonly="not is_edit and id"`.

### Sequence-Generated IDs

All master/transaction records use `ir.sequence`. Defined in each module's `data/sequence.xml`.

### Form Title Styling

All form `<div class="oe_title">` blocks must wrap the primary editable/display field in `<h1>` tags:

```xml
<div class="oe_title">
  <field name="reference_code" readonly="1"/>
  <h1>
    <field name="name" placeholder="..." readonly="state != 'draft'"/>
  </h1>
</div>
```

The `<h1>` gives the title a large, prominent appearance consistent across all forms. Fields that are reference/ID codes (like `name` as reference number) stay outside `<h1>` as plain `<field>`. The primary descriptive field (user-editable name, description, reference) goes inside `<h1>`.

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

**Asset Auto-Creation:** `accounting_move_asset` inherits `accounting.move`, overrides `action_post()` to call `_create_assets_from_move()` after posting. Scans debit lines for `is_asset_account=True` accounts and creates draft assets automatically.

### Create/Write State Detection Pattern

For auto-created records (delivery, receipt) that bypass action methods, use `create()` + `write()` to detect state transitions. Check `vals.get('state')` in write and check initial state in create. This handles both manual and programmatic paths.

### Many2one Dropdown Defaults (no_open / no_create)

All Many2one dropdown fields globally default to `no_open=True` and `no_create=True`. This is enforced at two layers:

**1. Server-side (primary)** — `_inject_m2o_no_open_create(doc, model_name, env)` is called from every mixin's `get_views()`:

- `NavigationMixin.get_views()` in `general`, `sales`, `employees`
- `PurchaseEditMixin.get_views()` in `purchases` (plus `bill.get_views()` and `receipt.get_views()`)
- `InventoryAccessMixin.get_views()` in `inventory`

The function parses the view XML via `lxml.etree`, finds all `<field>` tags whose model field is `many2one`, and merges `{'no_open': True, 'no_create': True}` into their `options` attribute using `ast.literal_eval` + `repr()` for safe round-tripping. Explicitly-set values are preserved via `dict.setdefault()`.

**2. Client-side (fallback)** — `general/static/src/js/many2one_defaults.js` patches `Many2OneField.prototype.setup()` to inject defaults before the component processes options. Loaded into `web.assets_backend` via `general/__manifest__.py`.

**Each module has its own local copy** of the helper function (named `_inject_m2o_no_open_create` or `inject_m2o_no_open_create`) — no cross-module imports, avoiding `ModuleNotFoundError` during upgrades.

**Effect:** Users cannot open related records (external link button) or create new records ("Create and Edit...") from any dropdown field.

**Opt-out per field** — explicitly set the option to `False` in the view XML:

```xml
<field name="partner_id" options="{'no_open': False, 'no_create': False}"/>
```

**When writing new views:** Do NOT add `options="{'no_open': True, 'no_create': True}"` on individual `<field>` tags — it's redundant noise. The global default already covers it. Only add `options` when you need to opt a specific field back in (set to `False`).

**When adding a new module with its own mixin/`get_views()`:** Copy the `_inject_m2o_no_open_create` helper function and add the injection loop (see existing mixins for the exact pattern).

---

# Appendix C: Purchases Service Bill — PRD

**Modul:** `purchases` (perubahan arsitektur), dengan dampak turunan ke `accounting`
**Status:** Confirmed — siap masuk tahap development
**Author:** Bono (dirancang bersama Claude)
**Tanggal:** 2026-07-31
**Terkait:** Prasyarat untuk `cost_supporting` sumber Purchases pada PRD "Sales Order Profitability Report"

## 1. Latar Belakang & Masalah

Berdasarkan `PRODUCT_SPEC.md` §5.8, seluruh alur akuntansi Purchase Bill di sistem ini memakai **satu-satunya jalur: Interim Approach**:

| Step | Journal Entry |
|---|---|
| Receipt | `Dr Stock Account / Cr 113200 (Stock Interim Received)` |
| Bill | `Dr 113200 (Stock Interim Received) / Cr 220000 (AP)` |
| Net Effect | `Dr Stock / Cr AP` (113200 nol lagi) |

Alur ini dibangun di atas asumsi bahwa setiap pembelian adalah **barang fisik** yang masuk ke Stock lewat Receipt. Konsisten dengan itu, katalog produk (`sales.product_type`) hanya mendukung 3 tipe: **Raw Materials / Semifinished / Finished Products** — tidak ada tipe "Service".

**Masalahnya:** saat perusahaan membeli **jasa** dari vendor eksternal untuk mendukung penjualan (mis. event organizer untuk acara peluncuran produk, freelance staff pameran, jasa logistik pihak ketiga di luar armada sendiri), tidak ada barang fisik yang bisa di-Receipt. Kalau dipaksakan lewat alur Purchase Order/Bill yang ada:

- Bill tetap wajib melalui Receipt untuk nge-net akun 113200 — padahal tidak ada barang yang diterima.
- Kalaupun di-skip, nilai Bill akan tersangkut selamanya di akun 113200/Stock — **tidak pernah tercatat sebagai expense**, karena mekanisme yang mengeluarkan nilai dari Stock ke expense (COGS) hanya terjadi saat barang itu **dijual dan di-deliver ke customer** (`sales_delivery_accounting`). Jasa tidak pernah "dijual dan dikirim" lewat mekanisme itu.

Ini bukan gap kecil — ini keterbatasan desain akuntansi Purchases Module itu sendiri. Solusinya adalah menambahkan **jalur akuntansi kedua** yang tidak melalui Stock Interim sama sekali.

## 2. Tujuan

1. Memungkinkan pencatatan pembelian **jasa** dari vendor lewat Purchases Module dengan akuntansi yang benar: **`Dr Expense / Cr Accounts Payable`** langsung saat Bill di-post — tanpa Receipt, tanpa menyentuh Stock/Stock Interim.
2. Tetap memakai infrastruktur yang sudah ada semaksimal mungkin: Approval Workflow, RBAC, Edit/Save Pattern, sequence, vendor management — supaya jasa vendor bernilai besar tetap melalui kontrol yang sama seperti pembelian barang.
3. Menyediakan cara **eksplisit** untuk men-tag pembelian jasa ini ke Sales Order tertentu (memakai field yang **sudah ada**: `purchases.purchase_order.sales_order_id`), sehingga bisa menjadi sumber `cost_supporting` pada laporan Sales Order Profitability Report di masa depan.

## 3. Non-Goals

- **Tidak** menambahkan tipe "Service" ke katalog produk (`sales.products`/`sales.product_type`) — katalog itu dipakai bersama oleh Sales (untuk dijual ke customer) dan tidak semestinya diubah untuk kebutuhan internal Purchases. Sebagai gantinya, dipakai master data baru khusus Purchases (lihat §4).
- **Tidak** membangun approval matrix terpisah untuk jasa — Service PO memakai `purchases.purchase_approval_matrix` yang sama dengan PO barang (berdasarkan `total_amount`).
- **Tidak** mendukung PO campuran (sebagian baris barang, sebagian baris jasa) — **dikonfirmasi tetap tidak dibutuhkan** untuk bisnis Distributor Kompresor: pembelian inti (unit kompresor, spare part) hampir selalu Goods, sementara jasa pendukung (instalasi vendor ketiga, kalibrasi, freight forwarder, EO) secara akuntansi harus tetap terpisah dari Stock walau dari vendor yang sama. Kalau 1 vendor menyediakan keduanya, solusinya buat 2 PO terpisah (Goods + Service) ke vendor yang sama — tidak ada friksi proses tambahan karena vendor master sudah mendukung banyak PO per vendor.
- **Tidak** menambahkan tracking "persentase jasa selesai" (partial service completion) — Bill jasa dibuat untuk nilai penuh PO, mirip pola Invoice "regular" (bukan DP%) di Sales.
- **Tidak** mengubah alur Auto-Procurement (RFQ otomatis dari SO untuk stock shortage) — itu tetap khusus untuk PO tipe Goods, tidak pernah men-generate Service PO secara otomatis.

## 4. Rancangan Data Model

### 4.1 Field baru: `purchases.purchase_order.order_type`

```python
order_type = fields.Selection(
    [('goods', 'Goods'), ('service', 'Service')],
    string='Order Type',
    default='goods',
    required=True,
)
```

- Default `'goods'` menjaga backward-compatibility — semua PO existing otomatis dianggap Goods, alur lama tidak berubah sama sekali.
- Field ini **mengunci** alur bisnis PO: Goods → wajib lewat Receipt; Service → langsung ke Bill tanpa Receipt.
- **Rekomendasi UX:** field ini hanya bisa diisi saat status `draft`, dikunci (`readonly`) setelah PO dikonfirmasi — supaya tidak ada PO yang "berubah pikiran" dari Goods jadi Service di tengah jalan (karena implikasi akuntansinya beda total).

### 4.2 Model baru: `purchases.service_category`

Mengikuti pola persis `accounting.petty.cash.category` (Expense Category) yang sudah ada:

```python
class PurchasesServiceCategory(models.Model):
    _name = 'purchases.service_category'
    _description = 'Purchases Service Category'

    category_name = fields.Char(string='Category Name', required=True)
    expense_account_id = fields.Many2one('accounting.account', string='Expense Account', required=True)
)
```

Contoh data: "Event Organizer", "Freelance Staff", "Jasa Logistik Pihak Ketiga", "Jasa Konsultan" — masing-masing dipetakan ke akun expense yang sesuai.

**Dikonfirmasi: pakai akun baru khusus**, bukan akun generik 510000 yang sama dengan Petty Cash — supaya biaya jasa vendor untuk mendukung penjualan bisa dipisah jelas di Chart of Accounts dari biaya operasional harian. Diusulkan kode akun **`530000 — Sales Support Service Expense`** (`account_type = expense`), mengikuti pola penomoran yang sudah ada (400000-an income, 500000-an expense; 500000 = COGS, 510000 = Petty Cash/Commission generic expense). Semua kategori jasa pada v1 bisa dipetakan ke satu akun ini dulu; kalau ke depan perlu granularitas per jenis jasa (mis. akun terpisah untuk Event Organizer vs Logistik), tinggal tambah akun baru dan arahkan `expense_account_id` masing-masing kategori ke situ — model `purchases.service_category` sudah dirancang fleksibel untuk itu tanpa perubahan kode.

### 4.3 Perubahan `purchases.purchase_order_line`

```python
service_category_id = fields.Many2one('purchases.service_category', string='Service Category')
description = fields.Char(string='Description')
```

- Saat `order_type = 'service'`: field `product_id` disembunyikan/`invisible`, `service_category_id` **wajib** diisi, `description` dipakai sebagai keterangan jasa. `qty_received`/`qty_to_receive` disembunyikan (tidak relevan, tidak ada Receipt).
- Saat `order_type = 'goods'`: perilaku sama seperti sekarang, `service_category_id` disembunyikan.

### 4.4 Link ke Sales Order — Field Sudah Ada, Tapi Perlu Dibuka untuk Input Manual

`purchases.purchase_order.sales_order_id` (Many2one) dan `sales_order_ids` (Many2many) **sudah ada** di sistem, tapi **dikonfirmasi murni diisi otomatis oleh proses Auto-Procurement saja** — tidak ada jalur untuk user mengisinya manual dari form PO saat ini.

**Perubahan yang dibutuhkan:** buka `sales_order_id` menjadi **writable** di form PO, khusus saat `order_type = 'service'` (untuk Goods PO, biarkan tetap readonly/auto-fill-only seperti sekarang, supaya tidak mengganggu perilaku Auto-Procurement yang sudah berjalan). Secara teknis:

```python
sales_order_id = fields.Many2one(
    'sales.sales_order',
    string='Sales Order',
)
```

Di level view, gunakan `attrs`/`invisible-readonly` kondisional terhadap `order_type`, bukan mengubah `readonly` Python-level secara permanen — supaya jalur Auto-Procurement untuk Goods PO tidak perlu disentuh sama sekali (tetap 100% backward-compatible).

## 5. Alur Bisnis

### 5.1 Service PO Flow

```
[Draft RFQ, order_type=service] ──Submit──> [Sent] ──Confirm Order──> [Purchase Order]
                                                                            │
                                                                (if approval needed,
                                                                 threshold sama dgn Goods PO)
                                                                            │
                                                                     [Wait Approval]
                                                                            │
                                                                    Approve/Revise/
                                                                    Return/Reject
                                                                            │
                                                                     [Approved]
                                                                            │
                                                                    Create Bill
                                                                    (TIDAK ada tombol
                                                                     "Receive Products")
                                                                            │
                                                                     [Draft Bill]
                                                                            │
                                                                    Confirm & Post
                                                                            │
                                                                     [Posted Bill]
                                                                    Dr Expense / Cr AP
                                                                    (langsung, tanpa Interim)
                                                                            │
                                                                    Register Payment
                                                                            │
                                                                       [Paid Bill]
```

Perbedaan kunci dari Goods PO: **tombol "Receive Products" tidak muncul** untuk `order_type = 'service'` — hanya "Create Bill" yang tersedia begitu PO berstatus Approved.

### 5.1a Sequence Terpisah untuk Service Bill

**Dikonfirmasi: pakai seri terpisah**, bukan menyatu dengan seri `BILL` yang sudah ada, supaya lebih mudah dibedakan di ledger/rekap tanpa harus buka detail tiap baris. Format **`SBILL######`** (mengikuti pola padding 6 digit yang sama seperti sequence `BILL` existing, demi konsistensi tampilan). Perlu ditambahkan entry sequence baru di data XML/model sequence, dan `purchases_bill_accounting_service` memilih sequence `SBILL` alih-alih `BILL` saat generate nomor dokumen untuk Bill dengan `order_type = 'service'` pada PO induknya.

### 5.2 Accounting Integration — `purchases_bill_accounting_service`

Polam baru, `_inherit='purchases.bill'`, override `action_post()`:

```python
def action_post(self):
    result = super().action_post()
    for bill in self:
        if bill.purchase_order_id.order_type == 'service':
            bill._create_service_accounting_move()
        # else: behavior lama (interim) tetap jalan lewat purchases_bill_accounting_interim
    return result

def _create_service_accounting_move(self):
    # Dr line.service_category_id.expense_account_id (per baris, sesuai kategori)
    # Cr 220000 (Accounts Payable) — total keseluruhan
    ...
```

Ini menghasilkan `accounting.move` dengan baris `account_type = 'expense'` — **konsisten dengan pola yang sudah dipakai** di Petty Cash Expense dan Commission, sehingga bisa langsung diikutsertakan di query laporan profitabilitas.

**Guard penting:** pastikan hook `purchases_bill_accounting_interim` (jalur lama) **tidak ikut jalan** untuk Bill dengan `order_type = 'service'` — kedua hook harus saling eksklusif berdasarkan `order_type`, supaya tidak terjadi double posting.

### 5.3 Validasi

- `order_type = 'service'` pada PO **wajib** semua baris punya `service_category_id` terisi (tidak boleh campur dengan `product_id`).
- Bill untuk Service PO tidak mensyaratkan `receipt_ids` — validasi "Create Bill" untuk Goods PO yang mengecek status Receipt **dilewati** untuk Service PO.
- Approval matrix tetap dievaluasi berdasarkan `total_amount`, sama seperti Goods PO — tidak ada perubahan logika approval.

## 6. UI / Menu

- **Form Purchase Order:** tambahkan field `order_type` di header (radio button atau selection dropdown), posisi awal form, `readonly` setelah `state != 'draft'`. Field `sales_order_id` dibuka writable **khusus saat `order_type = 'service'`** (lihat §4.4) — untuk Goods PO tetap readonly/auto-fill-only seperti perilaku sekarang.
- **Form Purchase Order Line:** conditional visibility `product_id` vs `service_category_id` + `description` berdasarkan `order_type` milik PO induk.
- **Tombol "Receive Products":** disembunyikan (`invisible`) untuk `order_type = 'service'`.
- **List View Purchase Orders / Vendor Bills:** tambahkan kolom/filter `Order Type` (Goods/Service) supaya user bisa memfilter dan membedakan sekilas.
- **Menu:** tidak perlu menu baru — Service PO dan Bill tetap muncul di menu yang sama (`Purchases → Orders → Purchase Orders`, `Purchases → Configuration → Vendor Bills`), cukup dibedakan lewat kolom/filter `Order Type`.
- **Master Data baru:** `Purchases → Configuration → Service Categories` — list + form sederhana (nama + akun expense).

## 7. RBAC

- **Tidak perlu flag permission baru** — reuse `can_create`/`can_update`/`can_confirm`/`can_billing` yang sudah ada untuk `purchases.purchase_order` dan `purchases.bill`. Perbedaan `order_type` adalah data, bukan boundary akses baru.
- **Master data `purchases.service_category`** butuh entry `general.menu` baru (untuk menu Configuration → Service Categories) dengan ACL CRUD standar.

## 8. Dampak ke PRD "Sales Order Profitability Report"

Setelah fitur ini diimplementasikan, query `cost_supporting` pada PRD tsb. perlu **ditambah satu sumber lagi**:

```sql
-- Purchases Service Bill yang di-tag ke SO (lewat PO.sales_order_id)
SELECT
    po.sales_order_id AS sale_order_id,
    SUM(aml.debit - aml.credit) AS cost_amount
FROM purchases_bill pb
JOIN purchases_purchase_order po ON po.id = pb.purchase_order_id
JOIN accounting_move am ON am.id = pb.move_id
JOIN accounting_move_line aml ON aml.move_id = am.id
JOIN accounting_account aa ON aa.id = aml.account_id
WHERE am.state = 'posted'
  AND po.order_type = 'service'
  AND po.sales_order_id IS NOT NULL
  AND aa.account_type = 'expense'
GROUP BY po.sales_order_id
```

Filter `po.order_type = 'service'` di sini eksplisit (bukan cuma mengandalkan `account_type = 'expense'`) supaya query tetap benar walau di masa depan Goods PO entah bagaimana punya baris expense juga.

Catatan: `sales_order_id` diambil dari **PO** (`po.sales_order_id`), bukan dari Bill. Untuk kasus `sales_order_ids` (M2M, multi-SO), v1 laporan ini **tidak mendukung alokasi proporsional otomatis** — kalau satu Service PO didukung untuk >1 SO, disarankan pakai `sales_order_id` (single).

## 9. Pengujian

| Kategori | Skenario |
|---|---|
| `happy_path` | Buat Service PO, isi `service_category_id` + `sales_order_id`, approve, Create Bill langsung tanpa Receipt, post → move `Dr Expense / Cr AP` benar |
| `no_receipt_button` | Service PO Approved → tombol "Receive Products" tidak muncul; hanya "Create Bill" |
| `goods_unaffected` | Goods PO (order_type default) → alur lama (Receipt → Bill interim) tidak berubah sama sekali |
| `validation` | Service PO line tanpa `service_category_id` → gagal validasi/tidak bisa submit |
| `no_double_post` | Bill service tidak memicu hook interim — hanya satu move yang dibuat |
| `tagging` | `sales_order_id` di Service PO ter-propagate benar ke Bill lewat `purchase_order_id` |
| `rbac_master_data` | User tanpa akses menu Service Categories tidak bisa CRUD `purchases.service_category` |

## 10. Ringkasan Perubahan Teknis

| File/Area | Perubahan |
|---|---|
| `purchases/models/purchase_order.py` | Tambah field `order_type` (Selection, default 'goods'); buka `sales_order_id` writable kondisional untuk `order_type='service'` |
| `purchases/models/purchase_order_line.py` | Tambah field `service_category_id`, conditional terhadap `product_id` |
| `purchases/models/service_category.py` | Model baru `purchases.service_category` |
| `purchases/models/bill.py` | Override `action_post()` untuk jalur akuntansi service (`Dr Expense / Cr AP`) dengan guard; pilih sequence `SBILL` |
| `purchases/data/` | Sequence baru `SBILL######` |
| `accounting/data/` | Akun baru `530000 — Sales Support Service Expense` |
| `purchases/views/` | Update form PO (field `order_type`, `sales_order_id` writable kondisional, visibility `service_category_id`/`product_id`), sembunyikan tombol Receive untuk service, form + list view `purchases.service_category` |
| `purchases/security/ir.model.access.csv` | ACL untuk `purchases.service_category` |
| `general/data/` | Entry `general.menu` baru untuk `Purchases → Configuration → Service Categories` |
| `tests/` | Test suite sesuai §9 |

## 11. Status

**Siap masuk tahap development.**

---

# Appendix D: Sales Order Profitability Report — PRD

**Modul:** `accounting` (report utama), dengan perubahan field pendukung di `accounting` (Petty Cash Expense)
**Status:** Confirmed
**Author:** Bono (dirancang bersama Claude)
**Tanggal:** 2026-07-30

## 1. Latar Belakang & Masalah

Sistem saat ini mencatat Pendapatan dan Biaya (COGS) secara otomatis ke `accounting.move`:

- **Pendapatan** — dibuat oleh `sales_invoice_accounting._create_accounting_move()` saat Sales Invoice di-post: `Dr AR / Cr Sales Revenue / Cr Tax + Commission`.
- **Biaya (COGS)** — dibuat oleh `sales_delivery_accounting` saat Delivery mencapai state `done`: `Dr expense_account_id / Cr stock_account_id`.

Laporan yang tersedia sekarang (**Profit And Loss**, SQL view di modul `accounting`) hanya agregat perusahaan pada rentang tanggal tertentu — **tidak bisa di-breakdown per Sales Order**. Untuk mengetahui profitabilitas satu proyek penjualan (satu SO), user harus membuka SO → buka Invoice terkait → buka Journal Entry-nya → lakukan hal yang sama untuk Delivery → jumlahkan manual. Proses ini tidak scalable dan rawan salah hitung ketika satu SO punya banyak Invoice/Delivery parsial.

## 2. Tujuan

Menyediakan laporan **"Sales Order Profitability"** yang menampilkan, per Sales Order:

- Total Pendapatan (dari seluruh Invoice yang sudah posted terkait SO tsb.)
- Total Biaya (COGS produk + biaya komisi + biaya pendukung penjualan via Petty Cash yang di-tag + Purchases Service Bills yang di-tag — lihat §5.1)
- Margin (Rp) dan Margin (%)

Laporan mengikuti pola **SQL View Report Model** yang sudah dipakai untuk Trial Balance / General Ledger / Balance Sheet / Profit And Loss.

## 3. Non-Goals

- Biaya operasional/overhead umum (mis. Office Supplies, biaya kantor rutin) **tetap tidak masuk** margin per SO — hanya masuk P&L perusahaan. Biaya pendukung penjualan (entertainment, transportasi klien, dll.) **hanya ikut terhitung jika secara eksplisit di-tag ke SO tsb.** oleh user saat input Petty Cash Expense. Biaya jasa vendor eksternal lewat Purchases **hanya masuk jika di-tag lewat Sales Order ID di PO Service** (lihat PRD "Purchases Service Bill").
- Tidak mengganti laporan Profit And Loss yang sudah ada; ini laporan tambahan yang lebih granular.
- Tidak menghitung profitabilitas per baris produk (line-level) pada versi pertama — scope awal per SO (header-level).

## 4. Konfirmasi Data Model

- `sales.invoice.sales_order_id` dan `sales.delivery.sales_order_id` **sudah ada** di source code — tidak perlu field baru/migrasi.
- Margin per SO **wajib memasukkan biaya komisi** (`accounting.commission.plan` / `accounting.commission.settlement`).
- Sistem ini adalah proyek **Odoo 17 custom modules (Bonoworx)** — terpisah dari pekerjaan WordPress GINDING/Sahabat Aqiqah.

**Gap yang ditemukan:** `accounting.petty.cash.expense` **tidak punya field yang menghubungkannya ke Sales Order**. Supaya biaya semacam ini bisa ikut masuk margin per SO, perlu ditambahkan field baru:

- `accounting.petty.cash.expense.sales_order_id` — Many2one → `sales.sales_order`, **opsional** (nullable). Saat user mengisi expense yang memang untuk mendukung penjualan tertentu, field ini diisi. Expense yang murni overhead kantor dibiarkan kosong.

**`purchases.purchase_order` sudah punya `sales_order_id`** dan sudah didukung oleh PRD "Purchases Service Bill" yang menambahkan jalur `Dr Expense / Cr AP` langsung. `cost_supporting` v1 bersumber dari **Petty Cash Expense yang di-tag + Purchases Service Bills yang di-tag**.

## 5. Rancangan Data Model

### 5.1 Model baru: `accounting.sales_profitability_report`

```python
class AccountingSalesProfitabilityReport(models.Model):
    _name = 'accounting.sales_profitability_report'
    _description = 'Sales Order Profitability Report'
    _auto = False
    _order = 'sale_order_date desc'

    sale_order_id = fields.Many2one('sales.sales_order', string='Sales Order', readonly=True)
    sale_order_name = fields.Char(string='SO Number', readonly=True)
    sale_order_date = fields.Date(string='Order Date', readonly=True)
    customer_id = fields.Many2one('sales.customer', string='Customer', readonly=True)
    total_revenue = fields.Monetary(string='Total Revenue', readonly=True)
    cost_cogs = fields.Monetary(string='COGS', readonly=True)
    cost_commission = fields.Monetary(string='Commission Cost', readonly=True)
    cost_supporting = fields.Monetary(string='Supporting Cost', readonly=True)
    total_cost = fields.Monetary(string='Total Cost', readonly=True)
    margin_amount = fields.Monetary(string='Margin', readonly=True)
    margin_percent = fields.Float(string='Margin (%)', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    so.id AS id,
                    so.id AS sale_order_id,
                    so.sales_code AS sale_order_name,
                    so.create_date AS sale_order_date,
                    so.customer_id AS customer_id,
                    COALESCE(rev.total_revenue, 0) AS total_revenue,
                    COALESCE(cogs.cost_amount, 0) AS cost_cogs,
                    COALESCE(comm.cost_amount, 0) AS cost_commission,
                    COALESCE(supp.cost_amount, 0) AS cost_supporting,
                    COALESCE(cogs.cost_amount, 0) + COALESCE(comm.cost_amount, 0)
                        + COALESCE(supp.cost_amount, 0) AS total_cost,
                    COALESCE(rev.total_revenue, 0)
                        - (COALESCE(cogs.cost_amount, 0) + COALESCE(comm.cost_amount, 0)
                           + COALESCE(supp.cost_amount, 0)) AS margin_amount,
                    CASE
                        WHEN COALESCE(rev.total_revenue, 0) = 0 THEN 0
                        ELSE ((COALESCE(rev.total_revenue, 0)
                               - (COALESCE(cogs.cost_amount, 0) + COALESCE(comm.cost_amount, 0)
                                  + COALESCE(supp.cost_amount, 0)))
                              / rev.total_revenue) * 100
                    END AS margin_percent,
                    (SELECT id FROM res_currency LIMIT 1) AS currency_id
                FROM sales_sales_order so

                -- Revenue: baris income pada move Invoice
                LEFT JOIN (
                    SELECT inv.sales_order_id AS sale_order_id,
                           SUM(aml.credit - aml.debit) AS total_revenue
                    FROM sales_invoice inv
                    JOIN accounting_move am ON am.id = inv.move_id
                    JOIN accounting_move_line aml ON aml.move_id = am.id
                    JOIN accounting_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND aa.account_type = 'income'
                    GROUP BY inv.sales_order_id
                ) rev ON rev.sale_order_id = so.id

                -- COGS: baris expense pada move Delivery
                LEFT JOIN (
                    SELECT dl.sales_order_id AS sale_order_id,
                           SUM(aml.debit - aml.credit) AS cost_amount
                    FROM sales_delivery dl
                    JOIN accounting_move am ON am.id = dl.move_id
                    JOIN accounting_move_line aml ON aml.move_id = am.id
                    JOIN accounting_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND aa.account_type = 'expense'
                    GROUP BY dl.sales_order_id
                ) cogs ON cogs.sale_order_id = so.id

                -- Komisi: baris expense pada move Invoice
                LEFT JOIN (
                    SELECT inv.sales_order_id AS sale_order_id,
                           SUM(aml.debit - aml.credit) AS cost_amount
                    FROM sales_invoice inv
                    JOIN accounting_move am ON am.id = inv.move_id
                    JOIN accounting_move_line aml ON aml.move_id = am.id
                    JOIN accounting_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND aa.account_type = 'expense'
                    GROUP BY inv.sales_order_id
                ) comm ON comm.sale_order_id = so.id

                -- Biaya Pendukung Penjualan: Petty Cash Expense yang di-tag + Purchases Service Bills yang di-tag
                LEFT JOIN (
                    -- Source 1: Petty Cash Expenses
                    SELECT pce.sales_order_id AS sale_order_id,
                           SUM(aml.debit - aml.credit) AS cost_amount
                    FROM accounting_petty_cash_expense pce
                    JOIN accounting_move am ON am.id = pce.move_id
                    JOIN accounting_move_line aml ON aml.move_id = am.id
                    JOIN accounting_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND aa.account_type = 'expense'
                      AND pce.sales_order_id IS NOT NULL
                    GROUP BY pce.sales_order_id
                    UNION ALL
                    -- Source 2: Purchases Service Bills (linked via PO.sales_order_id)
                    SELECT po.sales_order_id AS sale_order_id,
                           SUM(aml.debit - aml.credit) AS cost_amount
                    FROM purchases_bill pb
                    JOIN purchases_purchase_order po ON po.id = pb.purchase_order_id
                    JOIN accounting_move am ON am.id = pb.move_id
                    JOIN accounting_move_line aml ON aml.move_id = am.id
                    JOIN accounting_account aa ON aa.id = aml.account_id
                    WHERE am.state = 'posted'
                      AND po.order_type = 'service'
                      AND po.sales_order_id IS NOT NULL
                      AND aa.account_type = 'expense'
                    GROUP BY po.sales_order_id
                ) supp ON supp.sale_order_id = so.id
            )
        """)
```

> **Catatan:** nama tabel/kolom tetap perlu disesuaikan dengan nama kolom exact di source code. Filter `am.state = 'posted'`, `account_type = 'income'`/`expense`, dan `po.order_type = 'service'` adalah bagian stabil dari desain.

### 5.2 Filter status

- Hanya SO dengan invoice **posted** dan delivery **done** yang dihitung — SO yang masih draft/tanpa transaksi tampil dengan Revenue/Cost = 0.

## 6. Wizard — Filter Laporan

**Model:** `accounting.sales_profitability_report.wizard` (TransientModel)

| Field | Tipe | Keterangan |
|---|---|---|
| `date_from` | Date | Filter tanggal order dari |
| `date_to` | Date | Filter tanggal order sampai |
| `customer_id` | Many2one → `sales.customer` | Opsional, filter per customer |
| `sale_order_ids` | Many2many → `sales.sales_order` | Opsional, filter SO tertentu |

Tombol **"Tampilkan"** membuka list view dengan domain filter via context.

## 7. UI / Menu

- **Menu:** `Accounting → Reporting → Sales Order Profitability`
- **List View:** kolom SO Number, Customer, Order Date, Total Revenue, COGS, Commission Cost, Supporting Cost, Total Cost, Margin, Margin %.
- **Drill-down:** klik baris SO → buka form Sales Order terkait.
- **Cetak PDF:** `qweb-html`, tombol Print bawaan Odoo.
- **Form Petty Cash Expense:** tambahkan field `sales_order_id` (Many2one, opsional) di form `accounting.petty.cash.expense`.

## 8. Integrasi RBAC

1. Entry baru di `general.menu` — `sales_profitability_report` dengan `ir_ui_menu_id` ter-set.
2. ACL read-only (`ir.model.access.csv`) untuk model `accounting.sales_profitability_report` dan wizard-nya.

## 9. Fase Berikutnya (Out of Scope v1)

- **Line-level breakdown**: profitabilitas per produk dalam satu SO.
- **Export Excel** selain PDF.
- **Dashboard/grafik** trend margin per bulan.

## 10. Pengujian

| Kategori | Skenario |
|---|---|
| `happy_path` | SO dengan 1 invoice posted + 1 delivery done → revenue/cost/margin benar |
| `partial` | SO dengan invoice/delivery parsial → sum benar |
| `no_transaction` | SO draft tanpa invoice/delivery → revenue/cost = 0 |
| `edge_case` | Invoice/delivery dibatalkan → tidak ikut terhitung |
| `supporting_cost_tagged` | Petty Cash Expense di-tag ke SO + posted → masuk cost_supporting |
| `supporting_cost_service_bill` | Service Bill di-tag ke SO (lewat PO.sales_order_id) + posted → masuk cost_supporting |
| `supporting_cost_untagged` | Petty Cash Expense tanpa sales_order_id → tidak muncul di SO manapun |
| `rbac` | User tanpa general.auth untuk menu ini → menu tidak muncul |
| `filter_wizard` | Filter by date range / customer menghasilkan subset yang benar |

## 11. Ringkasan Perubahan Teknis

| File/Area | Perubahan |
|---|---|
| `accounting/models/` | Model baru `accounting.sales_profitability_report` (SQL view) |
| `accounting/models/` | Tambah field `sales_order_id` di `accounting.petty.cash.expense` |
| `accounting/views/` | Tambah field `sales_order_id` di form view `accounting.petty.cash.expense` |
| `accounting/wizard/` | Wizard baru `accounting.sales_profitability_report.wizard` |
| `accounting/views/` | List view report + wizard form view |
| `accounting/security/ir.model.access.csv` | ACL read-only untuk model & wizard baru |
| `general/data/` | Entry baru di `general.menu` dengan `ir_ui_menu_id` ter-set |
| `tests/` | Test suite sesuai §10 |

---

**Status:** Siap masuk tahap development. `cost_supporting` v1 mencakup Petty Cash Expense + Purchases Service Bills (PRD "Purchases Service Bill"). Langkah pertama: verifikasi nama kolom exact langsung dari source code sebelum menulis `init()` final.
