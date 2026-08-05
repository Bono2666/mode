# MOdE ERP — Product Specification

**Version:** 1.0  
**Author:** Bonoworx  
**Platform:** Odoo 17.0 (Custom Modules)  
**License:** LGPL-3  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [RBAC & Security](#3-rbac--security)
4. [Sales Module](#4-sales-module)
5. [Purchases Module](#5-purchases-module)
6. [Inventory Module](#6-inventory-module)
7. [Accounting Module](#7-accounting-module)
8. [Assets Module](#8-assets-module)
9. [Employees Module](#9-employees-module)
10. [Cross-Module Integration](#10-cross-module-integration)
11. [Sequence Definitions](#11-sequence-definitions)
12. [Menu Structure](#12-menu-structure)
13. [Reporting](#13-reporting)

---

## 1. Executive Summary

### 1.1 Product Vision

MOdE (Mode by Bonoworx) is a **complete, custom-built ERP system** on top of Odoo 17.0, designed for Indonesian small-to-medium enterprises. It replaces Odoo's standard modules with a fully customized, opinionated business suite covering the entire order-to-cash and procure-to-pay lifecycle.

### 1.2 Target Users

| Role | Primary Functions |
|------|-------------------|
| **Sales Team** | Customer management, quotations, sales orders, invoicing, delivery tracking |
| **Purchasing Team** | Vendor management, RFQs, purchase orders, goods receipt, vendor bill payment |
| **Warehouse Team** | Stock management, transfers, inventory adjustments, cycle counting |
| **Accounting Team** | Journal entries, bank reconciliation, petty cash, financial reporting |
| **Finance Manager** | Balance sheet, P&L, trial balance, commission management |
| **Asset Manager** | Fixed asset lifecycle, depreciation, revaluation, disposal |
| **HR/Admin** | Employee records, user management |
| **System Admin** | Full access to all modules and configuration |

### 1.3 Key Differentiators

- **Custom RBAC System**: Granular per-menu, per-action permissions without Odoo security groups
- **Edit/Save Pattern**: All forms use a consistent Back/Edit/Save/Cancel/Delete UI paradigm
- **Many2one Lockdown**: Global `no_open`/`no_create` on all dropdown fields
- **Disable Autosave**: Odoo's autosave is patched out entirely
- **Approval Workflows**: Multi-level, sequential approval chains with email notifications
- **IDR-Native Accounting**: All amounts in Indonesian Rupiah with zero decimal places
- **Auto-Procurement**: Sales orders automatically generate purchase RFQs for out-of-stock items

---

## 2. System Architecture

### 2.1 Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Odoo 17.0 |
| Backend | Python 3.11 (Odoo ORM) |
| Frontend | OWL (Odoo Web Library) |
| Views | XML (form, tree, kanban, QWeb reports) |
| Database | PostgreSQL |
| Testing | Playwright + Pytest (27 E2E tests) |

### 2.2 Module Dependency Graph

```
disable_autosave  ←── base
general           ←── base, disable_autosave
employees         ←── base, general, disable_autosave
sales             ←── base, general, employees, disable_autosave, mail
purchases         ←── base, general, sales, employees, disable_autosave, mail
inventory         ←── base, general, sales, purchases, disable_autosave
accounting        ←── base, general, disable_autosave, sales, purchases
assets            ←── base, general, accounting, purchases, employees, disable_autosave
user_management   ←── base, general, disable_autosave
```

### 2.3 Module Summary

| Module | Purpose | Key Models | Lines of Code |
|--------|---------|------------|---------------|
| `disable_autosave` | Patches out Odoo autosave | prevent.model | ~200 |
| `general` | RBAC system, master data, user management | general.menu, general.auth, general.custom_users, NavigationMixin | ~1,200 |
| `employees` | Employee management | employees.employees | ~200 |
| `sales` | Full sales lifecycle | customer, products, sales_order, invoice, payment, delivery, approval matrix | ~3,845 |
| `purchases` | Full procurement lifecycle | vendor, purchase_order, bill, receipt, approval matrix | ~2,464 |
| `inventory` | Warehouse & stock management | warehouse, location, stock_move, transfer, adjustment | ~1,357 |
| `accounting` | Custom accounting engine | account, journal, move, move.line, bank.statement, petty.cash, commission | ~3,136 |
| `assets` | Fixed asset management | asset, depreciation_line, revaluation_line, disposal_wizard | ~1,259 |
| `user_management` | Placeholder | — | ~18 |

---

## 3. RBAC & Security

### 3.1 Architecture Overview

MOdE implements a **custom Role-Based Access Control** system separate from Odoo's native `ir.model.access` and `ir.rule`. All business models grant full CRUD at the ORM level; fine-grained control is enforced at the UI layer.

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│ general.menu │────▶│ general.auth │────▶│ general.custom_users │
│ (menu tree)  │     │ (permissions)│     │ (user wrapper)      │
└─────────────┘     └─────────────┘     └──────────────────┘
                                                 │
                                                 ▼
                                        ┌──────────────────┐
                                        │    res.users      │
                                        │ (Odoo native)     │
                                        └──────────────────┘
```

### 3.2 Core Models

| Model | Purpose |
|-------|---------|
| `general.menu` | Registry of all navigable menus with `menu_id` string codes, linked to `ir.ui.menu` via `ir_ui_menu_id` |
| `general.auth` | Permission assignment: user + menu + boolean action flags |
| `general.custom_users` | Wraps `res.users` with position, department, image fields |

### 3.3 Permission Flags

| Flag | Controls |
|------|----------|
| `can_create` | Create new records |
| `can_update` | Edit existing records |
| `can_delete` | Delete/cancel records |
| `can_submit` | Submit for approval |
| `can_send` | Send documents by email |
| `can_confirm` | Confirm transactions |
| `can_invoicing` | Create invoices and payments |
| `can_receive` | Receive goods |
| `can_billing` | Manage vendor bills |
| `can_commission` | Manage commission settlements |
| `can_dispose` | Dispose fixed assets |

### 3.4 Login-Time Menu Restriction

On every login, `_refresh_custom_menu_access()`:

1. Clears all existing `restrict_user_ids` for the user
2. Deletes auto-generated parent auth entries
3. Iterates all `general.menu` records
4. For menus **without** an auth entry → adds user to `ir.ui.menu.restrict_user_ids`
5. Auto-creates parent auth entries so folder menus remain navigable
6. Clears ORM cache to force menu tree reload

**Admin override**: Users in `base.group_system` bypass all restrictions.

### 3.5 Navigation Mixin

Every business model inherits `navigation.mixin`, providing:

- Computed `user_can_create`, `user_can_update`, `user_can_delete` per record
- `get_views()` injection: hides "New" button and sets `create="0"` when lacking permission
- Global Many2one lockdown: `no_open=True, no_create=True` on all dropdown fields
- Standard Back/Edit/Save/Cancel/Delete action methods

### 3.6 Form Header Button Standard

Every form follows a strict layout:

| # | Button | Condition |
|---|--------|-----------|
| 1 | **Back** | Always first (far left) |
| 2 | **Edit** (active) | Has `can_update` permission |
| 3 | **Edit** (disabled) | Lacks `can_update` permission |
| 4 | **Save** | In edit mode or new record |
| 5 | **Cancel** (discard-new) | New record |
| 6 | **Cancel** (discard-edit) | Editing existing |
| 7 | **Delete** (active) | Has `can_delete` permission |
| 8 | **Delete** (disabled) | Lacks `can_delete` permission |

All forms hide `.o_control_panel` via CSS. All sheet fields use `readonly="not is_edit and id"`.

---

## 4. Sales Module

### 4.1 Overview

Full sales lifecycle: Customer → Product → Quotation → Sales Order → Invoice → Payment → Delivery.

### 4.2 Master Data Models

| Model | Code | Key Fields |
|-------|------|------------|
| `sales.customer` | `sales.customer` | customer_id (CUST), customer_name, email, npwp, cust_category, cust_type, cust_area, payment_terms, sales_name, partner_id |
| `sales.cust_category` | `sales.cust_category` | category_id (CUSTCAT), category_name |
| `sales.cust_type` | `sales.cust_type` | type_id (CUSTTYP), type_name |
| `sales.cust_area` | `sales.cust_area` | area_id (CUSTARE), area_name |
| `sales.ship_to` | `sales.ship_to` | ship_id (SHIPTO), ship_name, customer_id |
| `sales.products` | `sales.products` | product_id (PROD), product_name, price (IDR), price_yen (JPY), base_price (computed), reseller_price (computed), stock, product_category, product_unit, product_type, customer_tax, sales_ok, purchase_ok |
| `sales.product_type` | `sales.product_type` | name (Raw Materials / Semifinished / Finished Products) |
| `sales.product_category` | `sales.product_category` | category_name |
| `sales.product_unit` | `sales.product_unit` | uom, qty, base_uom, base_qty |
| `sales.taxes` | `sales.taxes` | name, tax_percentage, default_tax |
| `sales.payment_terms` | `sales.payment_terms` | payment_terms_id (PAYT), sales_text, early_discount, discount_percentage, discount_days, baseline_date, installment lines |
| `sales.price_condition` | `sales.price_condition` | price_name, date range, min_quantity, compute_price (fixed/discount), fixed_price, percent_price, applied_on, customer_applied_on |
| `sales.pricing_margin_config` | `sales.pricing_margin_config` | Singleton: reseller_margin (%), sales_margin (%) |
| `sales.exchange_rate` | `sales.exchange_rate` | currency_from, currency_to, rate |
| `sales.terms_and_conditions` | `sales.terms_and_conditions` | content (text, auto-populated on quotations) |

### 4.3 Transactional Models

| Model | Code | Key Fields |
|-------|------|------------|
| `sales.sales_order` | `sales.sales_order` | sales_code (SO), customer_id, state, is_quotation, payment_terms, sales_name, order_line_ids, invoice_ids, approval_log_ids |
| `sales.sales_order_line` | `sales.sales_order_line` | product_id, quantity, unit_price, taxes, base_discount, discount, sub_total, info (Indent) |
| `sales.invoice` | `sales.invoice` | invoice_number (INV), sales_order_id, customer_id, document_type (invoice/credit_note), invoice_type (regular/DP%/DP fixed), state, amount_untaxed, amount_tax, amount_total, amount_paid, amount_due |
| `sales.invoice.line` | `sales.invoice.line` | product_id, description, quantity, unit_price, discount, tax_id, sub_total, tax_amount, total |
| `sales.payment` | `sales.payment` | payment_number (PAY), invoice_id, customer_id, payment_date, payment_method, amount, state |
| `sales.delivery` | `sales.delivery` | delivery_number (DO), sales_order_id, customer_id, delivery_date, state, delivery_lines |

### 4.4 Business Flows

#### 4.4.1 Quotation Flow

```
[Draft] ──Submit──> [Wait Approval] ──All Approved──> [Approved]
    │                   │                                │
    │              Approve/Revise/                   Send by Email
    │              Return/Reject                         │
    │                                                   ▼
    │                                              [Sent]
    │                                                   │
    │                                              Confirm
    │                                                   │
    │                                                   ▼
    │                                          [Sales Order]
    │                                    (is_quotation=True,
    │                                     state=sale)
    └──Send by Email──> [Sent] ──Confirm──> [Sales Order]
```

**State notes:**
- `sent` is a permanent milestone marking that the quotation was emailed to the customer. Once `sent`, stock is **soft-reserved** (`qty_reserved_sale` counts open SO quantities, including those in `sent` state) and the **Confirm** button becomes available to convert to a Sales Order.
- The quotation can be re-sent by email from `sent` state; the state does not change further.

#### 4.4.2 Sales Order Flow

```
[Draft] ──Confirm──> [Sales Order (state=sale)]
    │
    └──Submit──> [Wait Approval] ──Approved──> Confirm ──> [Sale]
```

#### 4.4.3 Invoice Creation

```
[Confirmed SO] ──Create Invoice──> [Wizard: Regular / DP% / DP Fixed]
                                         │
                                         ▼
                                   [Draft Invoice] ──Confirm──> [Posted]
                                                                    │
                                                            Register Payment
                                                                    │
                                                                    ▼
                                                            [Posted Payment]
```

**Rules:**
- Only one draft invoice allowed at a time
- No down payment invoice after a regular invoice exists
- Down payment splits proportionally across lines

#### 4.4.4 Delivery Flow

```
[Sales Order] ──Create Delivery──> [Draft DO] ──Validate──> [Done]
```

#### 4.4.5 Send by Email (Quotation)

**Trigger:** "Send by Email" button on the quotation form.

**Availability:** Shown on `draft`, `approved`, and `sent` (re-send) states. Requires the user to have send permission, an existing record (not edit mode), no pending approval (if approval is required), and at least one order line.

**Flow:**

1. Opens the email compose wizard with a **customer selector** (`sales.customer`). The recipient email is resolved from the customer master data — not free-form partner addresses.
2. The email template auto-fills:
   - **Subject:** `Quotation {sales_code} - {customer_name}`
   - **From:** the salesperson's login email
   - **Body:** Indonesian-language quotation message with total amount
   - **Attachment:** PDF quotation (rendered by the SO QWeb report)
3. After the email is sent, a **chatter message** is posted to the quotation.
4. The state automatically transitions to **`sent`** (from `draft` or `approved`).
5. The user is redirected back to the Quotations list.

**Business effects of `sent`:**
- Stock is soft-reserved: `qty_reserved_sale` includes quantities from quotations in `sent` state.
- **Confirm** becomes available, converting the quotation to a Sales Order (`state = sale`).
- No accounting/journal entries are created by sending the email.

### 4.5 Approval Workflow

**Triggers:** Total amount exceeds approval matrix threshold OR discount exceeds base discount.

**Matrix Structure:**

| Field | Purpose |
|-------|---------|
| `sequence` | Order of approval (1, 2, 3...) |
| `name` | Approver (FK to custom_users) |
| `min_amount` | Amount threshold |
| `approve/revise/returned/reject` | Action permissions |
| `receive_return` | Can receive returned documents |
| `approved_as` | Role: proposer/checker/approver/validator/finalizer |

**Actions:**

| Action | Effect |
|--------|--------|
| Approve | Marks current step approved; advances to next; if last → SO goes to `approved` |
| Revise | Creates revised log; pending logs rebuilt from reviser's sequence |
| Return | Removes pending logs; finds prior approver with `receive_return=True` |
| Reject | SO goes to `cancel`; approval_status=`rejected` |

**Email notifications** sent to next pending approver on submit and after each action.

### 4.6 Pricing Logic

```
Product.base_price = Product.price × (1 + sales_margin / 100)
Product.reseller_price = Product.price × (1 + reseller_margin / 100)
```

**Price Condition Resolution (on product selection):**
1. Search matching conditions: date validity, customer match, min quantity
2. Sort by: customer_priority ASC, product_priority ASC, id DESC
3. Apply first match: fixed price → set unit_price; discount → set unit_price = base_price, apply percent discount
4. `base_discount` stores price-condition discount for approval comparison

### 4.7 Indent Logic

```
free_stock = product.stock - product.qty_reserved_sale
demand = total quantity for this product in current SO
info = "Indent" if demand > free_stock, else ""
```

- Auto-calculated on product selection and quantity change
- Preserves user-edited custom text on save

### 4.8 Product Import Wizard

| Feature | Detail |
|---------|--------|
| Format | CSV with 10 required columns |
| Encoding | Auto-detect: UTF-8, CP932, Shift-JIS, EUC-JP, Latin-1 |
| Delimiter | Auto-detect: comma, semicolon, tab |
| Batch size | 500 rows per batch |
| Price conversion | `price_idr = price_yen × exchange_rate` |
| Category | Auto-creates missing categories |
| Update | Matches by `product_id` to update existing products |

### 4.9 Journal Entry Generation

**Invoice posting:**

| Line Type | Account | Direction |
|-----------|---------|-----------|
| Receivable | 110000 (AR) | Debit (invoice) / Credit (credit note) |
| Revenue | 400000 (Sales Revenue) | Credit (invoice) / Debit (credit note) |
| Tax | 210000 (Tax Payable) | Credit (invoice) / Debit (credit note) |

**Payment posting:**

| Line Type | Account | Direction |
|-----------|---------|-----------|
| Liquidity | 100000 (Cash/Bank) | Debit |
| Receivable | 110000 (AR) | Credit |

Payment terms are respected: each installment creates a separate receivable line with its own `date_maturity`.

---

## 5. Purchases Module

### 5.1 Overview

Full procurement lifecycle: Vendor → RFQ → Purchase Order → Bill → Payment → Receipt.

### 5.2 Master Data Models

| Model | Code | Key Fields |
|-------|------|------------|
| `purchases.vendor` | `purchases.vendor` | vendor_id (VND), vendor_name, address, npwp, contact_name, telephone, email, payment_terms, partner_id |
| `purchases.service_category` | `purchases.service_category` | category_name, expense_account_id → `accounting.account` |

Vendor syncs bidirectionally with `res.partner` (create/write/unlink).

### 5.3 Transactional Models

| Model | Code | Key Fields |
|-------|------|------------|
| `purchases.purchase_order` | `purchases.purchase_order` | po_code (PO), vendor_id, buyer_id, **order_type** (goods/service, default goods), state, is_sent, entry_menu_code, sales_order_id, sales_order_ids (M2M), order_line_ids, bill_ids, receipt_ids, approval_log_ids |
| `purchases.purchase_order_line` | `purchases.purchase_order_line` | product_id, description, quantity, qty_received, qty_to_receive, unit_price, taxes, sub_total, **service_category_id** → `purchases.service_category` |
| `purchases.bill` | `purchases.bill` | bill_number (BILL), purchase_order_id, vendor_id, state, line_ids, amount_untaxed, amount_tax, amount_total, amount_paid, amount_due, payment_state |
| `purchases.receipt` | `purchases.receipt` | receipt_number (RCPT), purchase_order_id, vendor_id, state, line_ids |

### 5.4 Business Flow

```
[Draft RFQ] ──Submit──> [Sent] ──Confirm Order──> [Purchase Order]
                                                         │
                                                    (if approval needed)
                                                    Submit for Approval
                                                         │
                                                    [Wait Approval]
                                                         │
                                                    Approve/Revise/
                                                    Return/Reject
                                                         │
                                                    [Approved]
                                                         │
                                              Send by Email
                                              (is_sent = True,
                                               state unchanged)
                                                         │
                                                 is_sent = True
                                              (permanent gate)
                                                         │
                                          ┌──────────────┼──────────────┐
                                          ▼              ▼              ▼
                                  Receive Products  Create Bill      (re-send
                                          │              │          email)
                                          │              │              │
                                          ▼              ▼              │
                                    [Receipt]      [Draft Bill]         │
                                          │              │              │
                                     Validate      Confirm & Post       │
                                          │              │              │
                                          ▼              ▼              │
                                    [Stock Move]  [Posted Bill]         │
                                                         │              │
                                                 Register Payment       │
                                                         │              │
                                                         ▼              │
                                                 [Paid Bill]            │
                                                                        ▼
                                                                 [Sent PO]
```

**`is_sent` gate:** Send by Email sets the permanent `is_sent` flag (state does **not** change). Both **Receive Products** and **Create Bill** are hidden until `is_sent = True` — a PO must be emailed to the vendor before goods can be received or a bill created. `bill_status` becomes `to_bill` and `receipt_status` starts being computed only when `is_sent` is true.

#### 5.4.1 Send by Email (Purchase Order)

**Trigger:** "Send by Email" button on the PO form.

**Availability:** Shown on `purchase` and `approved` states. Requires the user to have send permission, no pending approval (if approval is required, must already be `approved`), and the receipt status must not be `partial`/`received` (cannot send after goods received).

**Flow:**

1. Validates state and send permission.
2. **Generates the PO PDF** explicitly (`PO - {po_code}.pdf`) and attaches it to the email; any previous attachment with the same name is deleted to avoid duplicates.
3. Resolves the sender email from buyer user → current user → company email (fallback in order).
4. Syncs the vendor's email to the linked `res.partner` if they differ.
5. Sets **`is_sent = True` permanently** before the wizard opens. The PO **state does not change**.
6. Opens the email compose wizard with a **vendor selector**. The template auto-fills:
   - **Subject:** `Purchase Order {po_code} - {company_name}`
   - **From:** buyer/current user/company email
   - **To:** vendor's email
   - **Body:** Indonesian-language PO message with total amount
   - **Attachment:** PO PDF
7. A **chatter message** is posted to the PO. No accounting/journal entries are created by sending.

**`is_sent` behavior:** The flag is permanent and irreversible. It acts as the master gate enabling downstream actions (Receive Products, Create Bill).

### 5.5 Approval Workflow

Identical structure to Sales approval:
- Sequential approval chain defined in `purchases.purchase_approval_matrix`
- Triggered when `total_amount` exceeds matrix threshold
- Same actions: Approve, Revise, Return, Reject
- Email notifications to next pending approver
- Full audit trail in `purchases.purchase_approval_log`

### 5.6 Procurement Integration (Auto-Create RFQ from SO)

**Trigger:** On `sales.sales_order.create()` and `write()`.

**Shortage Calculation (vendor-aware):**

Products are grouped by vendor before shortage is computed. Quantities from other SOs are only counted against available stock when those SOs' products share the same vendor. Products without a vendor have no cross-SO stock sharing.

```
available  = product.stock - (product.qty_reserved_sale - current_SO_need)
shortage   = max(0, need - available)
```

> `qty_reserved_sale` (product field) counts all open SO quantities in reserved states (`draft`, `sale_draft`, `wait_approval`, `approved`, `sent`, `sale`) and does not filter by vendor. The vendor-aware filtering is applied during shortage computation by comparing the vendors of the other open SO lines.

**RFQ Sync Logic:**
1. Get all linked RFQs in draft/sent state
2. Update existing lines to match shortage
3. Remove lines for products no longer needed
4. For new shortages: find existing RFQ for same product, or create new RFQ
5. Products **without a `vendor_id` still generate RFQs** (vendor field left empty). The vendor is validated on submission/confirmation: an RFQ/PO cannot be submitted or confirmed while `vendor_id` is empty.

**Multi-SO Support:** A PO can be linked to multiple SOs via `sales_order_ids` (Many2many). The `based_on_so` OWL widget renders clickable links to linked SOs.

### 5.7 Receipt Validation Rules

- Quantity must be > 0
- Cannot exceed `qty_to_receive` on the PO line
- On validation: `product.stock += line.quantity`
- Auto-creates `inventory.stock_move` records

### 5.8 Bill Accounting

#### 5.8.1 Interim Approach (Goods)

| Step | Journal Entry |
|------|---------------|
| Receipt | Dr Stock Account / Cr 113200 (Stock Interim Received) |
| Bill | Dr 113200 (Stock Interim Received) / Cr 220000 (AP) |
| **Net Effect** | Dr Stock / Cr AP (113200 nets to zero) |

#### 5.8.2 Service Approach (Service PO)

For `purchases.purchase_order.order_type = 'service'`:

| Step | Journal Entry |
|------|---------------|
| Bill (no receipt) | Dr 530000 (or `service_category_id.expense_account_id`) / Cr 220000 (AP) |

- The `_create_accounting_move` hook dispatches on `order_type`: service → expense path; goods → interim path (mutually exclusive — no double posting).
- Service bills use sequence **`SBILL######`**.
- `sales_order_id` on the PO is user-writable for Service POs, enabling future `cost_supporting` tagging in the Sales Order Profitability Report.

---

## 6. Inventory Module

### 6.1 Overview

Warehouse management, stock tracking, transfers (receipts/deliveries/internal), and inventory adjustments.

### 6.2 Core Models

| Model | Code | Key Fields |
|-------|------|------------|
| `inventory.warehouse` | `inventory.warehouse` | code (WH/0001), name |
| `inventory.location` | `inventory.location` | name, complete_name, usage (internal/supplier/customer/inventory/transit), warehouse_id |
| `inventory.stock_move` | `inventory.stock_move` | move_code (MOVE/000001), product_id, quantity, source_location_id, destination_location_id, type (incoming/outgoing/internal/adjustment), state, origin_model, origin_id |
| `inventory.transfer` | `inventory.transfer` | transfer_code, operation_type (incoming/outgoing/internal), source_location_id, destination_location_id, sales_order_id, purchase_order_id, state, line_ids |
| `inventory.transfer.line` | `inventory.transfer.line` | product_id, quantity, purchase_order_line_id, sales_order_line_id |
| `inventory.adjustment` | `inventory.adjustment` | adjustment_code (ADJ/000001), location_id, state, line_ids |
| `inventory.adjustment.line` | `inventory.adjustment.line` | product_id, current_qty, counted_qty, difference |

### 6.3 Location Types

| Type | Purpose | Example |
|------|---------|---------|
| `internal` | Stock within a warehouse | Main Warehouse/Stock |
| `supplier` | External vendor location | Vendor Location |
| `customer` | External customer location | Customer Location |
| `inventory` | Virtual location for adjustments | Inventory Adjustment |

### 6.4 Stock Move Types

| Type | Stock Effect |
|------|-------------|
| `incoming` | Product stock **increases** |
| `outgoing` | Product stock **decreases** (with insufficient stock check) |
| `internal` | No stock change (location transfer only) |
| `adjustment` | Stock changes by +/- signed quantity |

### 6.5 Transfer Validation Flow

```
[Draft Transfer] ──Validate──> [Done]
       │
       └──Cancel──> [Cancelled]
```

**On validation:**
1. Validates state is `draft` and lines exist
2. Checks quantity constraints (PO receipt: ≤ `qty_to_receive`; SO delivery: ≤ `qty_to_deliver`)
3. Creates `stock_move` for each line
4. Calls `action_done()` on each stock move (updates product stock)
5. Updates PO line `qty_received` or SO line `qty_delivered`
6. Auto-creates `purchases.receipt` (incoming) or `sales.delivery` (outgoing)
7. Auto-creates remaining transfer if unfulfilled quantities remain

### 6.6 Auto-Creation from PO/SO

| Source | Trigger | Transfer Type |
|--------|---------|---------------|
| `purchases.purchase_order.write()` | `receipt_status = 'to_receive'` and `qty_to_receive > 0` | incoming |
| `sales.sales_order.write()` | `state = 'sale'` and `qty_to_deliver > 0` | outgoing |

**Guard:** Only one draft transfer per PO/SO is allowed.

### 6.7 Inventory Adjustment Flow

```
[Draft Adjustment] ──Validate──> [Done]
       │
       └──Cancel──> [Cancelled]
```

**On validation:**
1. For each line, compute `difference = counted_qty - current_qty`
2. If difference > 0: stock move from "Inventory Adjustment" to location (gain)
3. If difference < 0: stock move from location to "Inventory Adjustment" (loss)
4. Each stock move is immediately marked done

**Adjustment Line Wizard:** Popup for adding/editing lines. Prevents duplicate products. Auto-saves parent adjustment after line changes.

### 6.8 Key Business Rules

| Rule | Description |
|------|-------------|
| Quantity > 0 | Stock moves must have positive quantity |
| No negative counted qty | Adjustment lines cannot have negative `counted_qty` |
| Insufficient stock check | Outgoing moves check `product.stock >= quantity` |
| No done record deletion | Done moves/transfers/adjustments cannot be deleted |
| One draft transfer per PO/SO | Prevents duplicate auto-creation |
| Remaining transfer auto-creation | After partial validation, new draft transfer created for unfulfilled lines |

### 6.9 Context-Based Integration Guards

| Context Flag | Purpose |
|-------------|---------|
| `skip_inventory_access` | Bypasses `general.auth` checks during auto-creation |
| `skip_product_stock_update` | Prevents stock update on stock move |
| `skip_auto_inventory_receipt_transfer` | Prevents PO write from re-triggering |
| `skip_auto_inventory_delivery_transfer` | Prevents SO write from re-triggering |

---

## 7. Accounting Module

### 7.1 Overview

Complete custom accounting engine (not using Odoo's built-in accounting). Double-entry bookkeeping, chart of accounts, journal entries, bank reconciliation, petty cash, commissions, and financial reporting.

### 7.2 Chart of Accounts

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

### 7.3 Journals

| Code | Name | Type | Default Accounts |
|------|------|------|------------------|
| SALE | Sales Journal | sale | Credit: 400000 |
| PURC | Purchase Journal | purchase | Debit: 500000 |
| CASH | Cash Journal | cash | Debit & Credit: 100000 |
| BANK | Bank Journal | bank | Debit & Credit: 100000 |
| GENERAL | Miscellaneous Journal | general | — |

### 7.4 Journal Entry Lifecycle

```
[Draft] ──Post──> [Posted] ──Cancel──> [Cancelled] ──Reset──> [Draft]
```

**Posting validation:**
1. State must be `draft`
2. Entry must be balanced (`abs(debit - credit) < 0.01`)
3. At least one journal item line
4. Entry date must fall within an **open** accounting period

### 7.5 Integration Auto-Posting

| Source Document | Trigger | Journal Entry |
|-----------------|---------|---------------|
| Sales Invoice (post) | `action_post()` | Dr AR / Cr Revenue / Cr Tax + Commission |
| Sales Payment (post) | `action_post()` | Dr Cash / Cr AR |
| Sales Delivery (done) | `create()`/`write()` | Dr Expense / Cr Stock (COGS) |
| Purchase Bill (post) | `action_post()` | Dr Stock Interim / Cr AP |
| Purchase Receipt (received) | `action_receive()` | Dr Stock / Cr Stock Interim |
| Vendor Bill Payment | `action_register_payment()` | Dr AP / Cr Cash |

### 7.6 Petty Cash System

**Models:**

| Model | Purpose |
|-------|---------|
| `accounting.petty.cash` | Fund master (code, name, journal, cash account, expense account, balance) |
| `accounting.petty.cash.category` | Expense category (name, expense_account_id) |
| `accounting.petty.cash.expense` | Cash expense/reimbursement (lines, total, state workflow, **sales_order_id** — optional link to SO for profitability tracking) |
| `accounting.petty.cash.topup` | Bank-to-petty-cash transfer |
| `accounting.petty.cash.transfer` | Inter-fund transfer |
| `accounting.petty.cash.settlement` | Employee advance return to petty cash |

**Workflows:**

| Type | States | Journal Entry |
|------|--------|---------------|
| Cash Expense | Draft → (Submit) → Wait Approval → Approved → Posted | Dr Expense / Cr Petty Cash |
| Top Up | Draft → (Submit) → Wait Approval → Approved → Posted | Dr Petty Cash / Cr Bank |
| Transfer | Draft → (Submit) → Wait Approval → Approved → Posted | Dr Dest Fund / Cr Source Fund |
| Settlement | Draft → (Submit) → Wait Approval → Approved → Posted | Dr Petty Cash / Cr Employee Advance |

**Approval workflow** follows the same pattern as the Purchases approval (`purchases.purchase_approval_matrix`), applied to Accounting documents via a shared `accounting.approval.mixin`:

- Approval chain defined in `accounting.approval.matrix` (per document type), building `accounting.approval.log` audit records.
- Submit from `draft` (`action_submit_for_approval`) → `wait_approval`; sequential Approve / Revise / Return / Reject via `accounting.approval.wizard` → `approved` → `posted`.
- Per-user action permissions computed from the matrix (`user_can_approve/revise/return/reject`, `user_can_submit`).
- Email notification sent to the next pending approver on submit and after each action.

**Default Fund:** MAIN — Main Office Cash (journal: Cash, cash account: 100500, expense account: 510000)

### 7.7 Commission System

**Commission Plan:**

| Field | Options |
|-------|---------|
| `type` | Percentage / Fixed |
| `based_on` | Untaxed / Total |
| `rate` | Rate value |
| `journal_id` | General journal |
| `expense_account_id` | Commission expense account |
| `payable_account_id` | Commission payable account |

**Flow:** Invoice posted → commission calculated → journal entry: Dr Commission Expense / Cr Commission Payable → settlement record auto-created and auto-posted.

### 7.8 Fiscal Year & Period Management

- Fiscal years with monthly periods (12 per year)
- Periods can be individually opened/closed
- Journal entries cannot be posted outside an open period
- Pre-seeded: Fiscal Year 2026 with all 12 months

---

## 8. Assets Module

### 8.1 Overview

Complete fixed asset lifecycle: acquisition → depreciation → revaluation → disposal. Three depreciation methods supported. Daily cron auto-posts depreciation entries.

### 8.2 Core Models

| Model | Code | Key Fields |
|-------|------|------------|
| `assets.model` | `assets.model` | name, method (straight_line/declining/declining_then_straight), method_number, method_period, method_progress_factor, account_asset_id, account_depreciation_id, account_depreciation_expense_id, journal_id |
| `assets.asset` | `assets.asset` | asset_number (ASSET000001), name, state, asset_model_id, original_value, salvage_value, depreciable_value, book_value, fair_value, acquisition_date, first_depreciation_date, custodian_id, location |
| `assets.depreciation_line` | `assets.depreciation_line` | sequence, depreciation_date, depreciation_value, accumulated_value, remaining_value, state, move_id |
| `assets.revaluation_line` | `assets.revaluation_line` | book_value_before, fair_value_after, surplus_deficit_value, remaining_useful_life, note, move_id |

### 8.3 Asset Lifecycle

```
[Draft] ──Confirm──> [Running] ──Pause──> [Paused] ──Resume──> [Running]
                          │                                          │
                          ├──Compute Depreciation                    │
                          │     (daily cron auto-posts)              │
                          │                                          │
                          ├──Revalue──> [Running] (new fair value)   │
                          │                                          │
                          ├──Dispose──> [Disposed] ◄── Paused ──────┘
                          │
                          └──Close──> [Closed]
```

### 8.4 Depreciation Methods

| Method | Formula | Notes |
|--------|---------|-------|
| **Straight Line** | `depreciable_value / method_number` per period | Equal amounts; last period absorbs rounding |
| **Declining Balance** | `remaining_book_value × method_progress_factor` per period | Diminishing value; last period absorbs remainder |
| **Declining then Straight** | `max(declining_calc, straight_line_calc)` per period | Switches to straight line when beneficial |

### 8.5 Depreciation Board

One row per period. On `action_post_depreciation()`:

```
Dr Depreciation Expense (520000)
    Cr Accumulated Depreciation (114900)
```

**Daily cron** (`action_post_due_entries`) auto-posts all draft depreciation lines where `date <= today` for running assets.

### 8.6 Revaluation

| Scenario | Journal Entry |
|----------|---------------|
| Surplus (fair > book) | Dr Asset / Cr Revaluation Surplus (320000) |
| Deficit (fair < book) | First reduces accumulated surplus; excess → Dr Impairment Loss (620000) / Cr Asset |

After revaluation, depreciation schedule is regenerated from new fair value.

### 8.7 Disposal

**Journal Entry:**

```
Dr Accumulated Depreciation (full amount)
Dr Cash/Bank (if sale_price > 0)
Cr Asset Account (full asset value)
Dr/Cr Gain/Loss on Disposal (420000)
```

### 8.8 Auto-Creation from Journal Entries

When any `accounting.move` is posted, the system scans all debit lines. For lines where `account_id.is_asset_account = True` and `debit > 0`, a new `assets.asset` is auto-created in Draft state.

### 8.9 Chart of Accounts Additions

| Code | Name | Type |
|------|------|------|
| 114000 | Fixed Assets - Vehicles/Machinery/Equipment | fixed_asset |
| 114900 | Accumulated Depreciation - Fixed Assets | fixed_asset |
| 520000 | Depreciation Expense | expense |
| 420000 | Gain/Loss on Asset Disposal | income |
| 320000 | Revaluation Surplus - Fixed Assets | equity |
| 620000 | Impairment Loss on Fixed Assets | expense |

---

## 9. Employees Module

### 9.1 Overview

Simple employee management with position and department references.

### 9.2 Model

| Model | Code | Key Fields |
|-------|------|------------|
| `employees.employees` | `employees.employees` | employee_id (EMP0001), employee_name, position_id, department_id, sales_code |

### 9.3 Business Flow

Standard CRUD: Create → Read → Update → Delete. No state machine or approval workflow.

### 9.4 References

| Reference | Source Module |
|-----------|---------------|
| `general.position` | general |
| `general.department` | general |

---

## 10. Cross-Module Integration

### 10.1 Accounting Auto-Posting Chain

```
Sales Invoice Posted
  → Dr AR (110000) / Cr Revenue (400000) / Cr Tax (210000) / Dr Expense + Cr Payable (Commission)

Sales Payment Posted
  → Dr Cash (100000) / Cr AR (110000)

Sales Delivery Done
  → Dr Expense (500000) / Cr Stock (113100) [COGS]

Purchase Receipt Received
  → Dr Stock (113100) / Cr Stock Interim (113200)

Purchase Bill Posted
  → Dr Stock Interim (113200) / Cr AP (220000)

Vendor Bill Payment
  → Dr AP (220000) / Cr Cash (100000)
```

### 10.2 Inventory ↔ Sales ↔ Purchases

```
Sales Order Confirmed
  → Auto-creates Delivery Transfer (outgoing)
  → On Validate: Stock Move (outgoing) → product.stock decreases
  → Auto-creates Sales Delivery (done)

Purchase Order Confirmed
  → Auto-creates Receipt Transfer (incoming)
  → On Validate: Stock Move (incoming) → product.stock increases
  → Auto-creates Purchase Receipt (received)
```

### 10.3 Procurement Auto-Create

```
Sales Order Created/Updated
  → Calculates shortage per product
  → Auto-creates RFQ for products with vendor_id and shortage > 0
  → Multi-SO support: one PO can serve multiple SOs
```

### 10.4 Asset Auto-Create

```
Any Journal Entry Posted
  → Scans debit lines for is_asset_account=True
  → Auto-creates assets.asset in Draft state
  → Requires manual confirmation before depreciation begins
```

### 10.5 Partner Synchronization

| Source | Target | Direction |
|--------|--------|-----------|
| `sales.customer` | `res.partner` | Bidirectional sync on create/write; cascade on delete |
| `purchases.vendor` | `res.partner` | Bidirectional sync on create/write; cascade on delete |

### 10.6 Sales Order Profitability — cost_supporting Sourcing

The `cost_supporting` field in the Sales Order Profitability Report (§13) aggregates two sources:

1. **Petty Cash Expense** — expenses where `sales_order_id IS NOT NULL` (manual tagging via new field on `accounting.petty.cash.expense`).
2. **Purchases Service Bills** — bills from POs with `order_type = 'service'` where `po.sales_order_id IS NOT NULL`. Uses the `purchases_bill_accounting_service` accounting hook (`Dr Expense / Cr AP` directly, no Stock Interim).

Both are joined via `UNION ALL` in the SQL view and filtered by `am.state = 'posted'` + `account_type = 'expense'`.

---

## 11. Sequence Definitions

| Entity | Module | Prefix | Padding | Example |
|--------|--------|--------|---------|---------|
| Customer Category | sales | CUSTCAT | 4 | CUSTCAT0001 |
| Customer Type | sales | CUSTTYP | 4 | CUSTTYP0001 |
| Customer Area | sales | CUSTARE | 4 | CUSTARE0001 |
| Ship To | sales | SHIPTO | 4 | SHIPTO0001 |
| Customer | sales | CUST | 4 | CUST0001 |
| Product | sales | PROD | 4 | PROD0001 |
| Payment Terms | sales | PAYT | 4 | PAYT0001 |
| Sales Order | sales | SO | 6 | SO000001 |
| Invoice | sales | INV | 6 | INV000001 |
| Payment | sales | PAY | 6 | PAY000001 |
| Delivery | sales | DO | 6 | DO000001 |
| Vendor | purchases | VND | 4 | VND0001 |
| Purchase Order | purchases | PO | 6 | PO000001 |
| Bill | purchases | BILL | 6 | BILL000001 |
| Service Bill | purchases | SBILL | 6 | SBILL000001 |
| Service Category | purchases | SVCAT | 4 | SVCAT0001 |
| Receipt | purchases | RCPT | 6 | RCPT000001 |
| Warehouse | inventory | WH/ | 4 | WH/0001 |
| Transfer (Internal) | inventory | TRF/ | 6 | TRF/000001 |
| Transfer (Receipt) | inventory | WH/IN/ | 6 | WH/IN/000001 |
| Transfer (Delivery) | inventory | WH/OUT/ | 6 | WH/OUT/000001 |
| Adjustment | inventory | ADJ/ | 6 | ADJ/000001 |
| Stock Move | inventory | MOVE/ | 6 | MOVE/000001 |
| Journal Entry | accounting | JE | 6 | JE000001 |
| Bank Statement | accounting | STM | 6 | STM000001 |
| Account Code | accounting | ACC | 6 | ACC000001 |
| Commission Plan | accounting | CP | 4 | CP0001 |
| Commission Settlement | accounting | CS | 4 | CS0001 |
| Petty Cash Expense | accounting | PCE | 4 | PCE0001 |
| Petty Cash Top Up | accounting | PCT | 4 | PCT0001 |
| Petty Cash Transfer | accounting | PCTR | 4 | PCTR0001 |
| Petty Cash Settlement | accounting | PCS | 4 | PCS0001 |
| Asset | assets | ASSET | 6 | ASSET000001 |
| Employee | employees | EMP | 4 | EMP0001 |
| Country | general | CTRY | 4 | CTRY0001 |
| State | general | STAT | 4 | STAT0001 |
| City | general | CITY | 4 | CITY0001 |
| District | general | DIST | 4 | DIST0001 |
| Position | general | POSI | 4 | POSI0001 |
| Department | general | DEPT | 4 | DEPT0001 |

---

## 12. Menu Structure

### 12.1 Home

```
Home (dashboard)
├── Configuration
│   ├── Users
│   └── Others → Countries / States / Cities / Districts / Positions / Departments
└── Approvals (placeholder)
```

### 12.2 Sales

```
Sales
├── Order
│   ├── Quotations
│   ├── Sales Orders
│   ├── Customers
│   └── Delivery Orders
├── Products
└── Import Products

Master Data
├── Customer → Customer Categories / Customer Types / Customer Areas
├── Product → Product Types / Product Categories / Unit of Measures
├── Invoicing → Payment Terms / Terms and Conditions
├── Taxes
├── Price Conditions
├── Pricing Margin
├── Exchange Rate
└── Approval → Sales Matrix

Approvals
└── Sales Approval (Waiting My Approval)
```

### 12.3 Purchases

```
Purchases
├── Orders
│   ├── RFQ
│   ├── Purchase Orders
│   ├── Vendors
│   └── Products
└── Configuration
    ├── Product Categories
    ├── Unit of Measures
    ├── Payment Terms
    ├── Vendor Bills
    ├── Service Categories
    └── Approval Matrix
```

### 12.4 Inventory

```
Inventory
├── Operations
│   ├── Receipt
│   ├── Delivery
│   ├── Inventory Adjustments
│   └── Stock Moves
├── Products
└── Configuration
    ├── Warehouses
    └── Locations
```

### 12.5 Accounting

```
Accounting
├── Transactions → Journal Entries
├── Banking → Bank Statements
├── Petty Cash → Cash Expenses / Top Ups / Transfers / Settlements
├── Ledger → Trial Balance / General Ledger / Aged Receivable
├── Reporting → Balance Sheet / Profit And Loss / Sales Order Profitability
├── Commissions → Commission Plans / Commission Settlements
├── Assets → Assets / Depreciation Report
└── Accounting Configuration
    ├── Chart of Accounts
    ├── Account Types
    ├── Journals
    ├── Fiscal Years
    ├── Periods
    ├── Petty Cash Funds
    ├── Expense Categories
    └── Asset Models
```

### 12.6 Employees

```
Employees
└── Employees
```

---

## 13. Reporting

### 13.1 Financial Reports (SQL Views)

| Report | Parameters | Content |
|--------|-----------|---------|
| **Trial Balance** | date_from, date_to, target_move | Account code, name, type, total debit, total credit, net balance |
| **General Ledger** | date_from, date_to, account_ids, target_move | Every posted journal line with full context |
| **Aged Receivable** | date_as_of, period_length | Partner balances bucketed by 0-30, 31-60, 61-90, 90+ days |
| **Balance Sheet** | date_as_of, target_move | Assets (Current/Fixed), Liabilities, Equity with auto-computed net income |
| **Profit and Loss** | date_from, date_to, target_move | Revenue vs Expenses with Net Profit/Loss |
| **Sales Order Profitability** | date_from, date_to, customer_id, sale_order_ids | Per-SO Revenue, COGS, Commission, Supporting Cost, Margin (Rs & %) — SQL view (`_auto = False`); `cost_supporting` sources: Petty Cash expenses tagged to SO + Purchases Service Bills tagged to SO; per-row drill-down via `sales_profitability_transaction` (per-document detail: Invoice, Delivery, Payment, Petty Cash, Service Bill) |

All reports use `qweb-html` rendering. Odoo's Print button generates PDF.

### 13.2 Asset Reports

| Report | Content |
|--------|---------|
| **Asset Register** | Full list with original value, method, book value, status |
| **Depreciation Schedule** | Per-asset depreciation board |
| **Revaluation History** | Per-asset revaluation audit trail |

### 13.3 Reports Access

All financial report models are **read-only** (`_auto = False` with SQL views). Report wizards are transient models for parameter input only.

---

## Appendix A: Key Patterns

### A.1 Edit/Save Pattern

`is_edit` Boolean + `action_edit()`/`action_save()`. Fields: `readonly="not is_edit and id"`.

### A.2 Wizard Confirmation Pattern

Model's `action_<name>()` validates state → opens TransientModel wizard → `action_<name>_confirm()` calls back to `action_<name>_final()`.

### A.3 Accounting Auto-Posting Pattern

`_inherit` on source models, override `action_post()` to call `super()` then `_create_accounting_move()`. Smart button links to the move.

### A.4 Create/Write State Detection Pattern

For auto-created records (delivery, receipt) that bypass action methods, use `create()` + `write()` to detect state transitions via `vals.get('state')`.

### A.5 SQL View Report Models

`_auto = False`. `init()` does `CREATE OR REPLACE VIEW`. All fields `readonly=True`. Read-only in security ACLs.

---

## Appendix B: Testing

### B.1 Framework

- **Playwright + Pytest** (Python)
- Location: `tests/` directory
- 27 end-to-end tests

### B.2 Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Assets | 15 | Model CRUD, lifecycle, depreciation, revaluation, auto-creation |
| Product Import | 12 | Navigation, CSV upload, bulk import, error handling, edge cases |

### B.3 Running Tests

```bash
cd tests
pip install -r requirements.txt
playwright install chromium
pytest                                          # All tests
pytest -m asset                                 # Asset tests only
pytest -m happy_path                            # Import happy path
pytest -m error_handling                        # Import error handling
```

---

## Appendix C: Purchases Service Bill — PRD

**Modul:** `purchases` (perubahan arsitektur), dengan dampak turunan ke `accounting`
**Status:** Confirmed — siap masuk tahap development
**Author:** Bono (dirancang bersama Claude)
**Tanggal:** 2026-07-31
**Terkait:** Prasyarat untuk `cost_supporting` sumber Purchases pada PRD "Sales Order Profitability Report"

### 1. Latar Belakang & Masalah

Berdasarkan `PRODUCT_SPEC.md` §5.8, seluruh alur akuntansi Purchase Bill di sistem ini memakai **satu-satunya jalur: Interim Approach**:

| Step | Journal Entry |
|---|---|
| Receipt | `Dr Stock Account / Cr 113200 (Stock Interim Received)` |
| Bill | `Dr 113200 (Stock Interim Received) / Cr 220000 (AP)` |
| Net Effect | `Dr Stock / Cr AP` (113200 nol lagi) |

Alur ini dibangun di atas asumsi bahwa setiap pembelian adalah **barang fisik** yang masuk ke Stock lewat Receipt. Konsisten dengan itu, katalog produk (`sales.product_type`) hanya mendukung 3 tipe: **Raw Materials / Semifinished / Finished Products** — tidak ada tipe "Service".

**Masalahnya:** saat perusahaan membeli **jasa** dari vendor eksternal untuk mendukung penjualan (mis. event organizer, freelance staff, jasa logistik pihak ketiga), tidak ada barang fisik yang bisa di-Receipt. Kalau dipaksakan lewat alur Purchase Order/Bill yang ada, nilai Bill akan tersangkut selamanya di akun 113200/Stock — **tidak pernah tercatat sebagai expense**. Solusinya adalah menambahkan **jalur akuntansi kedua** yang tidak melalui Stock Interim sama sekali.

### 2. Tujuan

1. Pencatatan pembelian **jasa** dari vendor lewat Purchases Module dengan akuntansi yang benar: **`Dr Expense / Cr Accounts Payable`** langsung saat Bill di-post — tanpa Receipt, tanpa menyentuh Stock/Stock Interim.
2. Tetap memakai infrastruktur yang sudah ada: Approval Workflow, RBAC, Edit/Save Pattern, sequence, vendor management.
3. Menyediakan cara **eksplisit** untuk men-tag pembelian jasa ini ke Sales Order tertentu (memakai field yang **sudah ada**: `purchases.purchase_order.sales_order_id`).

### 3. Non-Goals

- **Tidak** menambahkan tipe "Service" ke katalog produk (`sales.products`/`sales.product_type`).
- **Tidak** membangun approval matrix terpisah untuk jasa.
- **Tidak** mendukung PO campuran (sebagian baris barang, sebagian baris jasa).
- **Tidak** menambahkan tracking "persentase jasa selesai" (partial service completion).
- **Tidak** mengubah alur Auto-Procurement.

### 4. Rancangan Data Model

#### 4.1 Field baru: `purchases.purchase_order.order_type`

```python
order_type = fields.Selection(
    [('goods', 'Goods'), ('service', 'Service')],
    string='Order Type',
    default='goods',
    required=True,
)
```

Default `'goods'` menjaga backward-compatibility. Field ini hanya bisa diisi saat status `draft`, dikunci setelah dikonfirmasi.

#### 4.2 Model baru: `purchases.service_category`

```python
class PurchasesServiceCategory(models.Model):
    _name = 'purchases.service_category'
    _description = 'Purchases Service Category'

    category_name = fields.Char(string='Category Name', required=True)
    expense_account_id = fields.Many2one('accounting.account', string='Expense Account', required=True)
```

**Akun expense:** `530000 — Sales Support Service Expense` (`account_type = expense`).

#### 4.3 Perubahan `purchases.purchase_order_line`

```python
service_category_id = fields.Many2one('purchases.service_category', string='Service Category')
description = fields.Char(string='Description')
```

Saat `order_type = 'service'`: `product_id` disembunyikan, `service_category_id` **wajib** diisi, `qty_received`/`qty_to_receive` disembunyikan.

#### 4.4 Link ke Sales Order

`purchases.purchase_order.sales_order_id` dibuka writable **khusus saat `order_type = 'service'`**. Untuk Goods PO tetap readonly/auto-fill-only.

### 5. Alur Bisnis

```
[Draft RFQ, order_type=service] ──Submit──> [Sent] ──Confirm──> [Purchase Order]
                                                                       │
                                                              Create Bill (TIDAK ada Receive Products)
                                                                       │
                                                              [Draft Bill] ──Post──> [Posted Bill]
                                                                       │
                                                              Dr Expense / Cr AP
```

**Sequence:** `SBILL######` (6 digit, terpisah dari `BILL`).

### 6. Accounting Integration

```python
def action_post(self):
    result = super().action_post()
    for bill in self:
        if bill.purchase_order_id.order_type == 'service':
            bill._create_service_accounting_move()
    return result

def _create_service_accounting_move(self):
    # Dr line.service_category_id.expense_account_id (per baris)
    # Cr 220000 (Accounts Payable)
    ...
```

Guard: kedua hook (interim + service) **saling eksklusif** berdasarkan `order_type`.

### 7. UI / Menu

- **Form PO:** field `order_type` di header, `readonly` setelah confirm; tombol "Receive Products" disembunyikan untuk service.
- **Master Data:** `Purchases → Configuration → Service Categories`

### 8. Dampak ke Sales Order Profitability Report

Query `cost_supporting` ditambah satu sumber:

```sql
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
```

### 9. Pengujian

| Kategori | Skenario |
|---|---|
| `happy_path` | Service PO → Bill → `Dr Expense / Cr AP` benar |
| `no_receipt_button` | Service PO → tombol Receive tidak muncul |
| `goods_unaffected` | Goods PO → alur lama tidak berubah |
| `validation` | Service PO tanpa `service_category_id` → gagal |
| `no_double_post` | Bill service hanya satu move |
| `tagging` | `sales_order_id` ter-propagate ke Bill |

---

## Appendix D: Sales Order Profitability Report — PRD

**Modul:** `accounting` (report utama)
**Status:** Confirmed
**Author:** Bono (dirancang bersama Claude)
**Tanggal:** 2026-07-30

### 1. Latar Belakang & Masalah

Laporan yang tersedia sekarang (**Profit And Loss**) hanya agregat perusahaan — **tidak bisa di-breakdown per Sales Order**. Untuk mengetahui profitabilitas satu SO, user harus buka Invoice → buka JE → buka Delivery → jumlahkan manual. Tidak scalable.

### 2. Tujuan

Laporan **"Sales Order Profitability"** yang menampilkan per Sales Order:
- Total Pendapatan (Invoice posted)
- Total Biaya (COGS + Komisi + Supporting Cost via Petty Cash tagged + Purchases Service Bills tagged)
- Margin (Rp) dan Margin (%)

### 3. Non-Goals

- Biaya overhead umum **tidak masuk** margin per SO.
- Tidak mengganti laporan P&L.
- Tidak menghitung profitabilitas per baris produk di v1.

### 4. Data Model

Field `accounting.petty.cash.expense.sales_order_id` (opsional, nullable) ditambahkan untuk tagging manual.

### 5. Model: `accounting.sales_profitability_report` (SQL View)

```python
class AccountingSalesProfitabilityReport(models.Model):
    _name = 'accounting.sales_profitability_report'
    _auto = False
    _order = 'sale_order_date desc'

    sale_order_id = fields.Many2one('sales.sales_order')
    sale_order_name = fields.Char()
    sale_order_date = fields.Date()
    customer_id = fields.Many2one('sales.customer')
    total_revenue = fields.Monetary()
    cost_cogs = fields.Monetary()
    cost_commission = fields.Monetary()
    cost_supporting = fields.Monetary()
    total_cost = fields.Monetary()
    margin_amount = fields.Monetary()
    margin_percent = fields.Float()
    currency_id = fields.Many2one('res.currency')
```

**Query `cost_supporting`:** UNION ALL dari Petty Cash Expense (tagged) + Purchases Service Bills (via PO.sales_order_id, order_type=service). Filter `am.state = 'posted'` + `account_type = 'expense'`.

**Drill-down method:** `action_view_transactions()` — returns `act_window` for `accounting.sales_profitability_transaction` filtered by current SO.

### 5a. Model: `accounting.sales_profitability_transaction` (SQL View, Detail)

Per-document transaction detail — one row per source document, accessed via "View Transactions" button on the profitability report form (per-row click). Also rendered in the PDF report per-SO.

```python
class AccountingSalesProfitabilityTransaction(models.Model):
    _name = 'accounting.sales_profitability_transaction'
    _auto = False

    sale_order_id = fields.Many2one('sales.sales_order')
    sale_order_name = fields.Char()
    sale_order_date = fields.Date()
    transaction_type = fields.Selection([
        ('invoice', 'Invoice'), ('delivery', 'Delivery'),
        ('payment', 'Payment'), ('petty_cash', 'Petty Cash'),
        ('service_bill', 'Service Bill'),
    ])
    category = fields.Selection([
        ('revenue', 'Revenue'), ('cogs', 'COGS'),
        ('commission', 'Commission'), ('supporting', 'Supporting Cost'),
        ('payment', 'Payment'),
    ])
    doc_number = fields.Char()
    doc_date = fields.Date()
    doc_state = fields.Char()
    amount = fields.Monetary()
    move_id = fields.Many2one('accounting.move')
    currency_id = fields.Many2one('res.currency')
```

**UNION ALL sources:** Invoice (posted) → revenue; Delivery (COGS move) → cogs; Invoice commission lines → commission; Payment (via invoice) → payment; Petty Cash (posted, tagged) → supporting; Service Bill (posted, service PO, tagged) → supporting. No menu entry — accessed via drill-down from the profitability report.

### 6. Wizard

`accounting.sales_profitability_report.wizard` — `date_from`, `date_to`, `customer_id` (optional), `sale_order_ids` (optional).

### 7. UI / Menu / RBAC

- **Menu:** `Accounting → Reporting → Sales Order Profitability`
- **List View:** kolom SO Number, Customer, Order Date, Revenue, COGS, Commission, Supporting Cost, Total Cost, Margin, Margin %.
- **Drill-down:** klik baris SO → form view profitability (read-only) → tombol "View Transactions" → list `accounting.sales_profitability_transaction` per SO (Invoice, Delivery, Payment, Petty Cash, Service Bill).
- **PDF:** `qweb-html` — termasuk tabel rincian transaksi per SO di bawah setiap baris.
- **RBAC:** `general.menu` entry + read-only ACL untuk `sales_profitability_report`, `sales_profitability_transaction`, dan wizard.

### 8. Pengujian

| Kategori | Skenario |
|---|---|
| `happy_path` | SO dengan invoice posted + delivery done → revenue/cost/margin benar |
| `partial` | Invoice/delivery parsial → sum benar |
| `no_transaction` | SO draft → revenue/cost = 0 |
| `supporting_cost_tagged` | Petty Cash di-tag ke SO → masuk cost_supporting |
| `supporting_cost_service_bill` | Service Bill di-tag ke SO → masuk cost_supporting |
| `supporting_cost_untagged` | Petty Cash tanpa tag → tidak muncul |
| `rbac` | Tanpa auth → menu tidak muncul |
| `filter_wizard` | Filter by date/customer → subset benar |

### 9. Ringkasan Perubahan Teknis

| File/Area | Perubahan |
|---|---|
| `accounting/models/` | Model baru `accounting.sales_profitability_report` (SQL view) + `accounting.sales_profitability_transaction` (SQL view, detail per-document) |
| `accounting/models/` | Tambah `sales_order_id` di `accounting.petty.cash.expense` |
| `accounting/views/` | Tambah `sales_order_id` di form petty cash expense |
| `accounting/views/` | Form view + tree view baru untuk profitability report (drill-down button) + tree view untuk transaction detail |
| `accounting/views/templates.xml` | PDF report: tambahkan tabel rincian transaksi per SO |
| `accounting/wizard/` | Wizard baru |
| `accounting/security/` | ACL read-only untuk report, transaction detail, dan wizard |
| `general/data/` | Entry `general.menu` baru |
| `tests/` | Test suite |

---

*End of Product Specification*
