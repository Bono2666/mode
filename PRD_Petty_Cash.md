# PRD - Petty Cash Module

## 1. Overview

### Objective

Membangun modul **Petty Cash** yang digunakan untuk mengelola kas kecil perusahaan dengan workflow yang jelas, approval, serta integrasi penuh dengan Accounting, Employees, Purchases, Sales, dan General Module.

Petty Cash harus mampu:

- Mencatat saldo kas kecil
- Melakukan top up
- Melakukan reimbursement
- Melakukan pengeluaran operasional
- Melakukan settlement
- Menghasilkan Journal Entry otomatis
- Menyediakan laporan kas kecil

---

## 2. Business Problem

Saat ini sistem sudah memiliki:

- Customer Payment
- Vendor Payment
- Bank Statement
- Journal Entry

Namun belum memiliki mekanisme untuk transaksi operasional kecil seperti:

- Beli ATK
- Parkir
- Bensin
- Makan meeting
- Transport
- Biaya kurir
- Fotokopi
- Pembelian mendadak

Jika semua dicatat langsung ke Journal Entry maka:

- Sulit melakukan monitoring saldo kas kecil
- Tidak ada histori pemegang kas
- Tidak ada approval
- Tidak ada audit trail

---

## 3. Scope

### Included

- Petty Cash Fund
- Cash Request
- Cash Expense
- Reimbursement
- Cash Settlement
- Cash Top Up
- Cash Transfer
- Journal Integration
- Reporting

### Excluded (Phase 2)

- Multi Currency
- OCR Receipt
- Mobile Upload
- Cash Forecast
- Budget Integration

---

## 4. Module Position

```text
Accounting
│
├── Transactions
│   ├── Journal Entry
│   ├── Bank Statement
│   └── Petty Cash
├── Banking
├── Ledger
└── Configuration
```

---

## 5. Master Data

### Petty Cash Account

Contoh:
- Main Office Cash
- Branch Tangerang
- Branch Bekasi
- Warehouse Cash
- Marketing Cash

Field:
- Code
- Name
- Responsible Employee
- Journal
- Default Expense Account
- Default Cash Account
- Current Balance
- Active

### Expense Category

Contoh:
- Transportation
- Office Supplies
- Meals
- Fuel
- Parking
- Courier
- Maintenance
- Entertainment

Field:
- Name
- Expense Account
- Tax

---

## 6. Transaction Types

### A. Cash Top Up

Bank → Petty Cash

Accounting:
```text
Dr Petty Cash
Cr Bank
```

### B. Cash Expense

Petty Cash → Expense

```text
Dr Expense
Cr Petty Cash
```

### C. Cash Transfer

Petty Cash A → Petty Cash B

```text
Dr Petty Cash B
Cr Petty Cash A
```

### D. Reimbursement

Employee → Petty Cash → Employee receives cash

```text
Dr Expense
Cr Petty Cash
```

### E. Settlement

Employee mengembalikan sisa uang.

```text
Dr Petty Cash
Cr Employee Advance
```

---

## 7. Main Model

```text
accounting.petty.cash
accounting.petty.cash.line
accounting.petty.cash.request
accounting.petty.cash.expense
accounting.petty.cash.settlement
accounting.petty.cash.transfer
accounting.petty.cash.category
```

---

## 8. Workflow

### Cash Expense

```text
Draft
↓
Submitted
↓
Approved
↓
Posted
↓
Cancelled
```

### Top Up

```text
Draft
↓
Approved
↓
Posted
```

### Settlement

```text
Draft
↓
Verified
↓
Posted
```

---

## 9. Status

- Draft
- Submitted
- Approved
- Rejected
- Posted
- Cancelled

---

## 10. Integration

### Employees Module

Menggunakan:
- Responsible Employee
- Requester
- Approver
- Receiver

### Accounting Module

Saat transaksi **Posted**:

Create Accounting Move → Link Move → Smart Button.

### Purchases

Purchase Order nominal kecil dapat dibayar menggunakan:

- Bank
- Cash
- Petty Cash

### Sales

Customer Refund dapat dilakukan melalui Petty Cash dan menghasilkan Journal otomatis.

### Inventory

Inventory Adjustment dapat menggunakan Petty Cash sebagai sumber biaya operasional.

---

## 11. Journal Integration

Setiap transaksi berstatus **Posted** akan menghasilkan Journal Entry otomatis.

### Expense

```text
Dr Office Supplies    150.000
Cr Petty Cash         150.000
```

### Top Up

```text
Dr Petty Cash       2.000.000
Cr Bank             2.000.000
```

### Transfer

```text
Dr Branch Cash
Cr Main Cash
```
