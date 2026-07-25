# 📦 Ah-Liki IMS — Complete Guide for Everyone
### Inventory Management System · Full Workflow & User Manual

---

> **Who is this guide for?**
> This guide is written for anyone who uses the Ah-Liki IMS — whether you are a cashier, a warehouse worker, a manager, or the administrator. **No technical knowledge is needed.** Every step is explained in plain language.

---

## 📋 TABLE OF CONTENTS

1. [What Is This System?](#1-what-is-this-system)
2. [The 7 User Roles — Who Does What?](#2-the-7-user-roles)
3. [How to Log In](#3-how-to-log-in)
4. [The Big Picture — How Everything Flows](#4-the-big-picture--how-everything-flows)
5. [Workflow 1 — Buying & Receiving Stock](#5-workflow-1--buying--receiving-stock)
6. [Workflow 2 — Selling to Customers (POS & Invoices)](#6-workflow-2--selling-to-customers)
7. [Workflow 3 — Dispatching Goods from the Warehouse](#7-workflow-3--dispatching-goods-from-the-warehouse)
8. [Workflow 4 — Managing the Warehouse (WMS)](#8-workflow-4--managing-the-warehouse-wms)
9. [Workflow 5 — Quotes](#9-workflow-5--quotes)
10. [Stock Alerts — When the System Warns You](#10-stock-alerts)
11. [Reports & Exports](#11-reports--exports)
12. [Managing Users (Admin Only)](#12-managing-users-admin-only)
13. [Managing Products, Suppliers & Categories](#13-managing-products-suppliers--categories)
14. [Quick Reference — What Each Role Can Do](#14-quick-reference--what-each-role-can-do)
15. [Glossary — Plain-English Definitions](#15-glossary)
16. [Frequently Asked Questions](#16-frequently-asked-questions)

---

## 1. What Is This System?

**Ah-Liki IMS** (Inventory Management System) is a computer program that helps your business:

| What it does | In plain words |
|---|---|
| Track your stock | Know exactly how many of each product you have at all times |
| Record purchases | Keep a log of every delivery that arrives |
| Process sales | Create invoices and receipts for customers |
| Manage the warehouse | Organise products on shelves using pallets |
| Warn you about problems | Alert you when stock is low or items are about to expire |
| Generate reports | Show you how well the business is doing |

Think of it as a **digital stockroom + cash register + warehouse manager**, all in one place.

---

## 2. The 7 User Roles

Every person who uses the system is given **one role**. Your role decides which parts of the system you can see and use.

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER ROLES                               │
├──────────────────┬──────────────────────────────────────────────┤
│  👑 Admin        │ Full access to everything. Manages all users. │
│  📊 Manager      │ Sees all reports & dashboard. Cannot sell.    │
│  💰 Finance      │ Can edit product prices. Sees reports.        │
│  🏭 Warehouse    │ Receives stock, adjusts stock, dispatches.    │
│  📦 WMS Operator │ Works in the warehouse — shelves & pallets.   │
│  🚚 WMS Dispatcher│ Confirms goods are loaded & sent out.        │
│  🛒 Cashier      │ Uses the till (POS) to sell to customers.     │
└──────────────────┴──────────────────────────────────────────────┘
```

> **Not sure what role you have?** Log in, click your name at the top right, and go to **My Profile**. Your role will be shown there.

---

## 3. How to Log In

1. Open your web browser (Chrome, Firefox, Edge, etc.)
2. Go to the address your administrator gave you (e.g. `http://localhost:8000` or your company's address)
3. You will see the **Login page**
4. Type your **Username** and **Password**
5. Click **Log In**

> ⚠️ **Forgot your password?** Contact your Administrator. They can reset it for you from the User Management section.

After logging in you will land on the **Dashboard** — the home page of the system.

---

## 4. The Big Picture — How Everything Flows

Here is the complete journey of goods through the business, from supplier to customer:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│   SUPPLIER          WAREHOUSE                  SALES                CUSTOMER    │
│                                                                                 │
│  ┌────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌────────────┐   │
│  │        │    │  1. Goods       │    │  4. Cashier     │    │            │   │
│  │ Goods  │───▶│     Arrive      │    │     makes a     │───▶│  Customer  │   │
│  │ Arrive │    │  (GRN Created)  │    │     SALE or     │    │  receives  │   │
│  │        │    │                 │    │     INVOICE      │    │   goods    │   │
│  └────────┘    │  2. Stock added │    └────────┬────────┘    └────────────┘   │
│                │     to system   │             │                               │
│                │                 │    ┌────────▼────────┐                      │
│                │  3. Pallets     │    │  5. Invoice     │                      │
│                │     placed on   │    │     goes to     │                      │
│                │     shelves     │    │     WAREHOUSE   │                      │
│                └─────────────────┘    │     for         │                      │
│                                       │     DISPATCH    │                      │
│                                       └────────┬────────┘                      │
│                                                │                               │
│                                       ┌────────▼────────┐                      │
│                                       │  6. Warehouse   │                      │
│                                       │     picks &     │                      │
│                                       │     loads goods │                      │
│                                       │     onto truck  │                      │
│                                       └─────────────────┘                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### The 6 Key Steps at a Glance

| Step | Who Does It | What Happens |
|------|------------|--------------|
| 1 | Warehouse Lead / WMS Operator | Goods arrive; a **GRN** (Goods Received Note) is created |
| 2 | System (automatic) | Stock numbers go **up** |
| 3 | WMS Operator | Products are put on **pallets** and placed on **shelves** |
| 4 | Cashier | A **Sale** or **Invoice** is created for a customer |
| 5 | System (automatic) | Invoice is queued for **dispatch** |
| 6 | Warehouse Lead / WMS Dispatcher | Goods are **picked**, loaded on truck, dispatch **confirmed** — stock goes **down** |

---

## 5. Workflow 1 — Buying & Receiving Stock

**Who does this:** Warehouse Lead, WMS Operator, Admin

This is what happens when a supplier delivers goods to your warehouse.

### Step-by-Step

```
DELIVERY ARRIVES
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1 — Go to the GRN section                     │
│  Menu → GRN (Goods Received Notes) → Add New GRN    │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2 — Fill in the form                          │
│  • Select the Supplier name                         │
│  • Add each product that was delivered              │
│  • Enter the quantity of each product               │
│  • (Optional) Enter batch number & expiry date      │
│  • Click SAVE                                       │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3 — System updates stock automatically        │
│  The system adds the received quantities to the     │
│  stock count. You will see a GRN number (e.g.       │
│  GRN-20240709-ABCD). Keep this number for records.  │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4 — Create Pallets (WMS Operators)            │
│  Go to WMS → Create Pallet                          │
│  Link the pallet to the GRN item you just received  │
│  Print the pallet label (has a QR code on it)       │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5 — Check Pallet into a Shelf                 │
│  Go to WMS → Check-In                               │
│  Scan the shelf QR code OR type the shelf code      │
│  Scan or enter the pallet lot number                │
│  Click Check In                                     │
└─────────────────────────────────────────────────────┘
```

### GRN Form Fields Explained

| Field | What it means |
|-------|---------------|
| **Supplier** | The company that delivered the goods |
| **Product** | Which product was delivered |
| **Quantity Received** | How many units arrived |
| **Batch Number** | Auto-generated by the system (tracking code) |
| **Expiry Date** | When the product expires (leave blank if it does not expire) |
| **Has Discrepancy** | Tick this if the delivery was wrong (wrong items or amounts) |
| **Notes** | Any extra comments about this delivery |

> ✅ **Good to know:** After saving a GRN, you will see the full GRN record with all items listed. The stock count for each product in the system will have already increased.

---

## 6. Workflow 2 — Selling to Customers

**Who does this:** Cashier, Admin

The Cashier uses the **POS (Point of Sale)** screen — this is your electronic cash register.

### Step-by-Step: Making a Sale

```
CUSTOMER ARRIVES AT COUNTER
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1 — Go to POS                                 │
│  Menu → POS Terminal (or it opens automatically)    │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2 — Find the products                         │
│  • Search by product name in the search bar         │
│  • OR browse by category using the buttons          │
│  • Click on a product to add it to the CART         │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3 — Set quantities & discounts                │
│  • In the cart on the right, adjust quantities      │
│  • Enter a % discount if needed                     │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4 — Enter customer details                    │
│  • Customer Name (optional for cash sales)          │
│  • Account Number (for credit customers)            │
│  • Payment Method: Cash / EFTPOS / Credit Account   │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5 — Complete the Sale                         │
│  Click "Complete Sale" button                       │
│  The system creates an INVOICE automatically        │
│  15% VAT/Tax is calculated automatically            │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 6 — Invoice is sent to warehouse              │
│  The invoice automatically appears in the           │
│  Warehouse Dispatch queue. The warehouse team       │
│  will pick and load the goods.                      │
└─────────────────────────────────────────────────────┘
```

### Payment Methods Explained

| Payment Method | When to use it |
|----------------|----------------|
| **Cash** | Customer pays in physical cash |
| **EFTPOS** | Customer pays by card (swipe/tap) |
| **Credit Account** | Customer has an account — they pay later. Enter their account number. |
| **Cheque** | Customer pays by cheque |

> 💡 **Tip:** If a customer buys regularly on credit, always enter their **Account Number**. This helps Finance track who owes money.

---

## 7. Workflow 3 — Dispatching Goods from the Warehouse

**Who does this:** Warehouse Lead, WMS Dispatcher, Admin

After a sale is made, the goods need to be physically picked from the warehouse and loaded onto a truck. This is called **Dispatch**.

### Step-by-Step: Dispatching an Order

```
INVOICE CREATED BY CASHIER
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 1 — View Dispatch Queue                       │
│  Menu → Warehouse → Dispatch                        │
│  You will see all orders waiting to be sent out     │
│  (Status: "Pending Dispatch")                       │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 2 — Open the invoice                          │
│  Click on the invoice number to see what needs      │
│  to be picked:                                      │
│  • Product names                                    │
│  • Quantities required                              │
│  • Available stock (system shows if stock is OK)   │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 3 — Pick the goods physically                 │
│  Go to the warehouse and physically collect each    │
│  item on the list. Use the Picking Ticket           │
│  (WMS → Picking Ticket) as a checklist.             │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 4 — Check off each item on the screen         │
│  Back on the dispatch screen:                       │
│  • Tick the checkbox next to each item              │
│    (only tick what you have physically picked)      │
│  • Enter the TRUCK PLATE NUMBER                     │
└─────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────┐
│  STEP 5 — Confirm Dispatch                          │
│  Click "Confirm Dispatch"                           │
│  ✓ Stock is automatically DEDUCTED from the system  │
│  ✓ Invoice status changes to "Dispatched"           │
│  ✓ A record is saved with who dispatched and when   │
└─────────────────────────────────────────────────────┘
```

### Important Rules for Dispatch

- ❌ You **cannot** confirm dispatch unless **every item is ticked**
- ❌ You **cannot** confirm dispatch if there is not enough stock
- ✅ Always enter the **truck plate number** before confirming
- ✅ You can add **comments** to the dispatch if there is anything unusual

### Dispatch Status Meanings

| Status | Meaning |
|--------|---------|
| **Pending Dispatch** | Sale made, goods not yet sent out |
| **Dispatched** | Goods loaded on truck and sent to customer |

---

## 8. Workflow 4 — Managing the Warehouse (WMS)

**WMS = Warehouse Management System** — this is the part of the system that tracks exactly WHERE each product is in the warehouse (which shelf, which pallet).

**Who does this:** WMS Operator, Warehouse Lead, Admin

### Understanding the Warehouse Layout

The warehouse is organised into **Shelf Locations**. Each shelf has a code like:

```
A1 = Aisle A, Level 1 (ground floor)
A2 = Aisle A, Level 2 (middle shelf)
A3 = Aisle A, Level 3 (top shelf)
B1 = Aisle B, Level 1
... and so on
```

Each shelf has a **QR code sticker** on it. You can scan this with a phone or tablet to check in pallets.

### Understanding Pallets

A **pallet** is a group of the same product stored together. Every pallet gets:
- A **Lot Number** (unique tracking code, e.g. `LOT-20240709-WXYZ`)
- A **printed label** with a QR code
- A **shelf location** in the warehouse

### WMS Workflows

#### A — Receiving & Placing Stock on Shelves

```
GRN is saved (stock received)
      │
      ▼
 WMS → Create Pallet
 (Select the product and GRN item, enter quantity)
      │
      ▼
 WMS → Print Pallet Label
 (Print and stick the label on the physical pallet)
      │
      ▼
 WMS → Check-In
 (Scan shelf QR code or type shelf code)
 (Enter pallet lot number)
 (Click Check In — pallet is now tracked at that shelf)
```

#### B — Moving a Pallet to a Different Shelf

```
 WMS → Transfer
 (Enter the Pallet Lot Number)
 (Enter the new Shelf Code)
 (Click Transfer — system updates the location)
```

#### C — Viewing What Is on Each Shelf

```
 WMS → Shelf List
 (Click on any shelf code to see what pallets are on it)
```

#### D — WMS Operator Dashboard

The WMS Operator has a simple dashboard showing:
- Recent check-ins
- Quick access to Check-In and Transfer functions

#### E — WMS Dispatcher Dashboard

The WMS Dispatcher can see:
- All pending invoices (orders to be dispatched)
- Dispatch confirmation tools

---

## 9. Workflow 5 — Quotes

A **Quote** is a price estimate you give a customer **before** they decide to buy. It lists the products and prices but does NOT reduce your stock.

**Who does this:** Cashier, Admin

### Step-by-Step: Creating a Quote

```
 POS → (use same screen as a regular sale)
 Add products to cart
 Fill in customer name
 Instead of "Complete Sale", use "Save as Quote"
      │
      ▼
 Quote is saved with status: DRAFT
      │
      ▼
 Quote can be:
   • Sent to customer for approval
   • Converted to an Invoice with ONE CLICK
     (Menu → Quotes → Open Quote → "Convert to Invoice")
```

### Quote Status Meanings

| Status | Meaning |
|--------|---------|
| **Draft** | Just created, not sent yet |
| **Sent** | Given to the customer |
| **Converted** | Customer agreed — turned into an Invoice |
| **Expired** | Time limit passed, no longer valid |

> 💡 **When to use a Quote:** When a customer asks "how much would it cost if I bought X, Y and Z?" — give them a quote first. If they agree, convert it to an invoice with one click. No need to re-enter anything.

---

## 10. Stock Alerts

The system automatically watches your stock and warns you when something needs attention.

### Types of Alerts

| Alert Type | What it means | What to do |
|------------|---------------|------------|
| 🟡 **Low Stock** | A product has fallen below its reorder level | Arrange a new order from the supplier |
| 🔴 **Expiry Warning** | A product batch expires within 30 days | Use or sell those items first |
| ⚠️ **GRN Discrepancy** | A delivery had wrong items or wrong amounts | Check with the supplier |

### How to View Alerts

- Go to **Menu → Alerts**
- You will see all open (unresolved) alerts at the top
- Resolved alerts are shown below

### How to Resolve an Alert

1. Click on the alert
2. Take the appropriate action (e.g. reorder the product)
3. Click **"Mark as Resolved"**
4. The alert is closed and saved with who resolved it and when

> 📍 **Dashboard:** The Dashboard also shows a summary of open alerts at the top. If you see a red number there, click it to view the alerts immediately.

### Setting Reorder Levels

Each product has a **Reorder Level** — the minimum quantity before the system warns you. For example, if a product has a reorder level of 10, you will get an alert when stock drops to 10 or below.

- **Admin** and **Finance** can change the reorder level when editing a product.
- Go to **Products → Edit Product → Reorder Level field**

---

## 11. Reports & Exports

**Who can see reports:** Admin, Manager

### Available Reports

Go to **Menu → Reports** to see:

| Report | What it shows |
|--------|---------------|
| **Total Stock Value** | How much all your current stock is worth in cost price |
| **Top Sellers** | Which products sell the most |
| **Monthly Sales** | How much revenue each month (last 6 months) |
| **Low Stock Items** | Products that need reordering |
| **Expiring Soon** | Products expiring within 30 days |

### Exporting Data to Excel/CSV

You can download data as a spreadsheet:

1. Go to **Reports**
2. Click **"Export Stock to CSV"** or **"Export Sales to CSV"**
3. The file downloads to your computer
4. Open it in Excel or Google Sheets

> 💡 **CSV files** open in Excel. Just double-click the downloaded file to open it.

### Dashboard Overview

The **Dashboard** (home page) shows a live summary:

| Dashboard Card | What it shows |
|----------------|---------------|
| **Total Products** | How many active products in the system |
| **Low Stock** | Products at or below reorder level |
| **Out of Stock** | Products with zero stock |
| **Sales Today** | Total sales value for today |
| **Sales Chart** | Bar chart of sales for the last 7 days |
| **Pending Dispatch** | Orders waiting to be sent out |
| **Stock Health** | Pie/bar breakdown of healthy vs low vs zero stock |

---

## 12. Managing Users (Admin Only)

**Only the Admin** can create, edit, or disable user accounts.

### Creating a New User

1. Go to **Menu → Users → Add User**
2. Fill in:
   - **Username** (e.g. `john.smith`) — this is what they type to log in
   - **First Name** and **Last Name**
   - **Email Address**
   - **Password** — choose a secure password and give it to the person privately
   - **Role** — select the correct role from the list (see Section 2)
3. Click **Save**

### Editing a User

1. Go to **Menu → Users**
2. Click **Edit** next to the user
3. You can change:
   - Their name, email
   - Their role
   - Their password (leave blank to keep existing password)
   - Whether their account is **Active** or **Disabled**

### Disabling a User

If someone leaves the company:
1. Go to **Menu → Users → Edit** (their account)
2. Untick the **"Active"** checkbox
3. Click Save — they can no longer log in

> ⚠️ **Security tip:** Never share passwords. Each person should have their own login. If someone leaves, disable their account immediately.

---

## 13. Managing Products, Suppliers & Categories

### Adding a New Product

**Who can do this:** Admin, Warehouse Lead

1. Go to **Menu → Products → Add Product**
2. Fill in:

| Field | What to enter |
|-------|---------------|
| **SKU** | Your unique product code (e.g. `RICE-5KG-001`) |
| **Name** | Full product name |
| **Category** | Which category group it belongs to |
| **Supplier** | Which supplier provides this product |
| **Unit Price** | The selling price (what you charge customers) |
| **Cost Price** | What you paid the supplier for it |
| **Reorder Level** | Minimum stock before an alert is triggered |
| **Unit** | How it is measured (each, kg, litre, carton, etc.) |
| **Barcode** | Barcode number if the product has one |

3. Click **Save**

### Adding a New Supplier

**Who can do this:** Admin only

1. Go to **Menu → Suppliers → Add Supplier**
2. Enter supplier name, contact person, phone, email, and address
3. Click **Save**

### Adding a New Category

**Who can do this:** Admin only

Categories help organise products (e.g. "Beverages", "Dry Goods", "Frozen").

1. Go to **Menu → Categories → Add Category**
2. Enter name and description
3. Click **Save**

### Editing a Product (Prices, Reorder Levels)

**Who can do this:** Admin, Finance

1. Go to **Menu → Products**
2. Find the product (use the search bar)
3. Click on the product name to open it
4. Click **Edit**
5. Make your changes and click **Save**

---

## 14. Quick Reference — What Each Role Can Do

| Feature | Admin | Manager | Finance | Warehouse | WMS Operator | WMS Dispatcher | Cashier |
|---------|:-----:|:-------:|:-------:|:---------:|:------------:|:--------------:|:-------:|
| Dashboard | ✅ | ✅ | ✅ | ✅ | — | — | ✅ |
| View Products | ✅ | ✅ | ✅ | ✅ | ✅ | — | ✅ |
| Add Products | ✅ | — | — | ✅ | — | — | — |
| Edit Products/Prices | ✅ | — | ✅ | — | — | — | — |
| Add Suppliers | ✅ | — | — | — | — | — | — |
| Add Categories | ✅ | — | — | — | — | — | — |
| Receive Stock (GRN) | ✅ | — | — | ✅ | ✅ | — | — |
| Adjust Stock | ✅ | — | — | ✅ | — | — | — |
| POS / Sales | ✅ | — | — | — | — | — | ✅ |
| Create Quotes | ✅ | — | — | — | — | — | ✅ |
| View Invoices | ✅ | — | — | — | — | — | ✅ |
| Warehouse Dispatch | ✅ | — | — | ✅ | — | ✅ | — |
| WMS Pallets/Shelves | ✅ | — | — | ✅ | ✅ | — | — |
| WMS Check-In | ✅ | — | — | ✅ | ✅ | — | — |
| WMS Transfer | ✅ | — | — | ✅ | ✅ | — | — |
| Reports | ✅ | ✅ | — | — | — | — | — |
| Export CSV | ✅ | — | — | — | — | — | — |
| View Alerts | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Resolve Alerts | ✅ | — | — | ✅ | — | — | — |
| Manage Users | ✅ | — | — | — | — | — | — |

---

## 15. Glossary

Plain-English definitions for every term used in the system.

| Term | Plain-English Meaning |
|------|-----------------------|
| **GRN** | Goods Received Note — a document created every time a delivery arrives at the warehouse. It records what came in, how much, from which supplier. |
| **SKU** | Stock Keeping Unit — a unique code for each product (like a product ID). |
| **Pallet** | A group of the same product stored together on a wooden/plastic platform. In the system, a pallet is a tracked bundle with its own lot number. |
| **Lot Number** | A unique tracking code for a specific pallet (e.g. `LOT-20240709-ABCD`). |
| **Shelf Location** | Where in the warehouse a pallet is stored (e.g. `A1`, `B3`). Shelves are arranged by aisle (A, B, C…) and level (1 = bottom, 2 = middle, 3 = top). |
| **Check-In** | The process of recording that a pallet has been placed on a specific shelf. |
| **Transfer** | Moving a pallet from one shelf to another and updating the system. |
| **POS** | Point of Sale — the electronic cash register screen used by cashiers to process sales. |
| **Invoice** | An official document listing what a customer bought, how much it costs, and the payment details. 15% tax is automatically added. |
| **Quote** | A price estimate given to a customer before they confirm their purchase. No stock is deducted. |
| **Dispatch** | The process of physically picking goods from the warehouse and loading them onto a delivery truck. |
| **Dispatch Status** | Whether an invoice's goods have been sent out yet (Pending = not yet, Dispatched = done). |
| **Reorder Level** | The minimum stock quantity for a product. When stock falls to or below this number, the system sends a Low Stock alert. |
| **Stock Adjustment** | A manual correction to the stock count (used when a physical count reveals a difference). |
| **Stock Movement** | Any change to the stock count — either goods coming in (GRN) or going out (sale/dispatch). |
| **Stock Value** | The total worth of your current stock, calculated as: current quantity × cost price. |
| **CSV** | A type of file that can be opened in Excel or Google Sheets. Used for exporting reports. |
| **VAT/Tax** | 15% tax automatically added to all invoices. |
| **Discrepancy** | When a delivery does not match what was expected (e.g. 10 items ordered but only 8 arrived). |
| **WMS** | Warehouse Management System — the part of the system that manages shelf locations, pallets, and warehouse operations. |
| **Picking Ticket** | A printed checklist used in the warehouse to pick all the items for a specific invoice. |
| **Account Number** | A reference number for credit customers who pay later (e.g. their business account code). |
| **EFTPOS** | Electronic payment by card (swipe, insert, or tap). |

---

## 16. Frequently Asked Questions

### Q: I made a sale but the stock has not gone down yet — is something wrong?
**A:** No, this is normal. When a cashier makes a sale, the invoice is sent to the warehouse for **dispatch**. The stock only goes down **after** the warehouse confirms the goods have been physically loaded and dispatched. Until then, the stock is reserved.

---

### Q: I created a GRN but the stock number looks wrong.
**A:** Check the quantity you entered on the GRN. Go to **Menu → GRN**, find the GRN record, and check the items listed. If the number is wrong, contact your Administrator — they may need to do a manual Stock Adjustment to correct it.

---

### Q: A customer says they have a credit account but I do not know their account number.
**A:** Ask your Manager or Administrator. They can look up the customer's account number. Always enter it correctly so Finance can track their balance.

---

### Q: I see a red alert saying "Low Stock" but we actually have plenty of that product.
**A:** The **Reorder Level** for that product may be set too high. Ask your Admin or Finance to edit the product and lower the Reorder Level to the correct number. Then the alert can be resolved.

---

### Q: Can I edit or delete an invoice after it has been created?
**A:** No. Once an invoice is created, it cannot be edited to maintain accurate records. If there was a mistake, contact your Administrator. They may need to void the invoice and create a new one.

---

### Q: What happens if I try to dispatch but there is not enough stock?
**A:** The system will show an error and will **not allow** the dispatch to go through. You will need to either receive more stock (GRN) or do a stock adjustment before trying again.

---

### Q: I forgot my password.
**A:** You cannot reset it yourself. Contact your **Administrator**. They go to **Menu → Users**, click Edit on your account, and enter a new password for you.

---

### Q: What does "Void" mean on an invoice?
**A:** It means the invoice has been cancelled. A voided invoice is kept in the records for accounting purposes but is no longer active.

---

### Q: How do I know where a product is in the warehouse?
**A:** Go to **Menu → Products**, find the product, and click on it. The product detail page shows all pallets linked to that product and which shelf each pallet is on. Alternatively, go to **WMS → Pallet List** and search by product name.

---

### Q: Can two people use the system at the same time?
**A:** Yes. Multiple users can be logged in at the same time. Each person uses their own login, and the system keeps track of who did what.

---

## 📞 Need More Help?

Contact your **System Administrator** for:
- Password resets
- New user accounts
- Unusual errors
- Corrections to incorrect records

---

*Ah-Liki IMS — Built to keep your stock under control.*
*Last updated: July 2026*
