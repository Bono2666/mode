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

**Product Form Conditional Visibility:**

- When `sales_ok = False` (product is not for sale), the following fields are hidden:
  - `reseller_price` (Reseller Price)
  - `base_price` + label + currency + tax_string (Sales Price)
  - `customer_tax` (Customer Tax)
- `remarks` field uses `colspan="2"` to span full width of the form
- Implemented via `invisible="not sales_ok"` on field, label, and div elements
- Applied to both Sales and Purchases product forms

### Purchases Module

**Flow:** RFQs → Purchase Orders → Bills + Receipts

Key models: `purchases.vendor`, `purchases.purchase_order`, `purchases.purchase_order_line`, `purchases.bill`, `purchases.bill.line`, `purchases.receipt`, `purchases.receipt.line`, approval matrix and wizard models.

**Procurement** (`sales_procurement.py`): Auto-creates RFQs from SOs for products with insufficient stock. Products without a configured vendor are silently skipped (no UserError).

### Inventory Module

Uses `InventoryAccessMixin`. Models: `inventory.warehouse`, `inventory.location`, `inventory.stock_move`, `inventory.transfer`, `inventory.adjustment`. Auto-creates transfers from PO/SO writes. Transfers validate → stock moves + delivery/receipt documents.

### Accounting Module

**Core models:** `accounting.account.type`, `accounting.account`, `accounting.journal`, `accounting.fiscal.year`, `accounting.period`, `accounting.move`, `accounting.move.line`, `accounting.bank.statement`, `accounting.bank.statement.line`, `accounting.commission.plan`, `accounting.commission.settlement`, `accounting.petty.cash`, `accounting.petty.cash.category`, `accounting.petty.cash.expense`, `accounting.petty.cash.topup`, `accounting.petty.cash.transfer`, `accounting.petty.cash.settlement`.

**Sales/Purchases integration** (via `_inherit`):

- `sales_invoice_accounting` — `_create_accounting_move()`: Dr AR / Cr Revenue / Cr Tax + Commission lines
- `sales_payment_accounting` — Dr Cash / Cr AR
- `purchases_bill_accounting` — Original expense-based bill move
- `purchases_payment_register_accounting` — Dr AP / Cr Cash

**Report Wizards + SQL Views:** Trial Balance, General Ledger, Aged Receivable, Balance Sheet, Profit And Loss. Reports render as `qweb-html` with PDF printable via Odoo's Print button.

**Chart of Accounts (17 accounts):**
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

**Menu structure:**

```
Accounting
├── Transactions → Journal Entries
├── Banking → Bank Statements
├── Petty Cash → Cash Expenses / Top Ups / Transfers / Settlements
├── Ledger → Trial Balance / General Ledger / Aged Receivable
├── Reporting → Balance Sheet / Profit And Loss
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
| Cash Expense | Draft → Submitted → Approved → Posted → Cancelled | `Dr Expense / Cr Petty Cash` |
| Top Up | Draft → Approved → Posted | `Dr Petty Cash / Cr Bank` |
| Transfer | Draft → Approved → Posted | `Dr Dest Fund / Cr Source Fund` |
| Settlement | Draft → Verified → Posted | `Dr Petty Cash / Cr Employee Advance` |

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
- Amount: `delivery_line.quantity × product.price`
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

### Balance Sheet & Profit And Loss

- **Balance Sheet:** SQL view with Assets (Current/Fixed Asset sub-groups), Liabilities, Equity. Retained Earnings = account 310000 balance + Net Income.
- **Profit And Loss:** SQL view with Revenue / Expenses sections, Net Profit/Loss.
- Both use `qweb-html` report type; Odoo Print button generates PDF.
- Wizards provide date filters (passed via context).

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
