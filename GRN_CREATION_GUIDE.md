# Ah Liki IMS — Complete Stock Flow Guide
### Products In → Stored → Products Out

---

## Overview

```
SETUP (one-time)
  Add Supplier → Add Category → Add Product

STOCK IN
  1. Create GRN  (goods received note)
  2. Create Pallets from GRN
  3. Check-in Pallets to Shelf

STOCK OUT
  Path A — Walk-in / Counter sale
    POS Terminal → Sale recorded → Stock deducted immediately

  Path B — Account / Delivery customer
    POS → Quote (optional) → Invoice → Warehouse Dispatch → Stock deducted
```

---

## Part 0 — One-Time Setup

Before any stock can move, three records must exist in the system.

### 0A · Add a Supplier
**Menu:** Suppliers → Add Supplier

| Field | Example |
|---|---|
| Name | Pacific Foods Ltd |
| Contact Name | Sam Fono |
| Phone | +685 20000 |
| Email | sam@pacificfoods.ws |

### 0B · Add a Category
**Menu:** Categories → Add Category

| Field | Example |
|---|---|
| Name | Canned Goods |
| Description | Tinned and preserved food items |

### 0C · Add a Product
**Menu:** Products → Add Product

| Field | Notes |
|---|---|
| **SKU** | Unique code e.g. `TUNA-185G` |
| **Name** | Product display name |
| **Category** | Pick from list |
| **Supplier** | **Must be set** — controls GRN filtering |
| **Unit Price** | Selling price (SAT$) |
| **Cost Price** | What you paid |
| **Reorder Level** | Alert fires when stock drops to or below this number |
| **Unit** | each / kg / carton / litre |
| **Barcode** | Optional — enables barcode scan at POS |

> **Key rule:** A product without a Supplier will not appear in the GRN form.

---

## Part 1 — Stock IN: Receiving Goods

### Step 1 · Create a GRN

**Who:** Admin · Warehouse · WMS Operator  
**Menu:** GRN → New GRN

**1. GRN Header**

| Field | What to enter |
|---|---|
| **Supplier** *(required)* | Select the supplier — product list filters automatically |
| **Received At** | Defaults to now; change if backdating |
| **Purchase Order** | Link to PO if one was raised — leave blank otherwise |
| **Notes** | Delivery comments, container number, driver name |
| **Has Discrepancy** | Tick if physical count differs from the PO or delivery note |

> The GRN number (e.g. `GRN-250710-001`) is generated automatically — you do not type it.

**2. Items Received** — one row per product line

| Column | What to enter |
|---|---|
| **Product** | Type name or SKU to search |
| **Qty Received** | Actual units counted on the dock |
| **Expiry Date** | Required for perishables; leave blank for non-perishables |

Click **Add Row** for each additional product. Tick **✕** to remove a row.

**3. Save**

Click **✅ Save GRN & Update Stock**.

The system automatically:
- Assigns the GRN number
- Assigns a batch number to every line
- Adds the quantities to stock
- Creates stock movement records (`Stock In`)
- Fires low-stock or expiry alerts if thresholds are crossed

**4. GRN Detail Page**

After saving you land on the detail page. You will see:

| Element | Meaning |
|---|---|
| **QR Code** (top-left) | Encodes the GRN number — scan to return to this record |
| **⚠ Discrepancy badge** | Only shows if you flagged a discrepancy |
| **Items table** | Product · Qty · Batch · Expiry · Unit Cost |
| **📦 Create Pallets** button | Proceed directly to pallet creation |

---

### Step 2 · Create Pallets

**Who:** Admin · Warehouse · WMS Operator  
**Menu:** GRN Detail → 📦 Create Pallets  
or: WMS → Pallets → New Pallet

Each pallet = a physical pallet or storage unit on your floor.

| Field | What to enter |
|---|---|
| **Product** | Pre-filled from GRN |
| **Quantity** | Units on this pallet |
| **Expiry Date** | Carried over from GRN item |
| **GRN Item** | Links the pallet back to the receiving record |
| **Notes** | Any notes (e.g. "damaged corner") |

After saving, a **pallet label with QR code** is printed automatically. The QR code contains the lot number (e.g. `LOT-250710-001`).

---

### Step 3 · Check-In Pallets to Shelf

**Who:** WMS Operator  
**Menu:** WMS → Check-In

Scan or type the **lot number** (from the pallet QR code), then select a **shelf location** (e.g. `A1`, `B3`).

The system records the location and marks the pallet as active at that shelf.

> Shelf locations are labelled by letter (A–Z) and story (1–3). Check the Shelf QR prints (WMS → Shelves) to see what's available.

**Stock is now physically stored and digitally tracked.**

---

## Part 2 — Stock OUT: Selling Goods

There are two paths depending on the customer type.

---

### Path A — Walk-In / Counter Sale (immediate)

**Who:** Admin · Cashier  
**Menu:** POS Terminal

1. Search or scan products into the cart.
2. Set quantity and apply discounts if needed.
3. Enter **Customer Name** (or leave blank for walk-in).
4. Select **Payment Method**: Cash · EFTPOS · Credit Account.
5. Click **Complete Sale**.

The system:
- Creates a Sale record with a sale number (e.g. `SALE-20250710-001`)
- Deducts stock immediately
- Fires low-stock alerts if any product drops below its reorder level

---

### Path B — Account / Delivery Customer (invoice + dispatch)

This path has three sub-steps: Quote (optional) → Invoice → Dispatch.

#### B1 · Quote *(optional)*

**Menu:** POS → Save as Quote

Use a quote when a customer wants a price before committing.

| Field | Notes |
|---|---|
| Customer Name | Account holder |
| Account Number | BC account code |
| Valid Until | Quote expiry date |
| Items + Discounts | Add product lines with optional % discount |

Save → the quote gets a number (e.g. `QTE-...`). No stock is reserved.

When the customer confirms, open the quote and click **Convert to Invoice** — one click copies everything across.

#### B2 · Invoice

**Menu:** POS → Complete Sale (creates invoice automatically)  
or: from a converted Quote

An invoice is created with:
- Status: **Unpaid**
- Dispatch Status: **Pending Dispatch**
- 15% VAT calculated automatically

**No stock is deducted yet** — that happens at dispatch.

Mark the invoice **Paid** when payment is received (cash/EFTPOS/cheque).

#### B3 · Warehouse Dispatch

**Who:** Admin · Warehouse · WMS Dispatcher  
**Menu:** Warehouse → Dispatch

The dispatch queue shows all invoices with status **Pending Dispatch**.

1. Open the invoice from the queue.
2. Review the **dispatch checklist** — each line shows product, qty required, and whether stock is sufficient.
3. Physically pick the items from the shelves.
4. Tick off each line as you load.
5. Enter the **Truck Plate** number.
6. Click **Confirm Dispatch**.

The system:
- Deducts stock for every line
- Records who dispatched and at what time
- Updates invoice dispatch status to **Dispatched**
- Fires low-stock alerts on affected products

> **Important:** All lines must be ticked and all products must have sufficient stock before dispatch can be confirmed.

---

## Part 3 — Monitoring

### Stock Movements
**Menu:** Stock → Movements

Every `Stock In` (GRN) and `Stock Out` (Sale / Dispatch) is logged here with a reference number, timestamp, and who performed it.

### Alerts
**Menu:** Alerts

| Alert Type | Triggered when |
|---|---|
| **Low Stock** | Product stock ≤ reorder level |
| **Expiry Warning** | A batch expires within 30 days |
| **GRN Discrepancy** | You flagged a discrepancy on a GRN |

Resolve an alert by clicking **Resolve** — it records who resolved it and when.

### Reports
**Menu:** Reports *(Admin / Manager only)*

| Report | What it shows |
|---|---|
| Stock Value | Total value of current inventory |
| Top Sellers | Products by units sold |
| Monthly Sales | Revenue last 6 months (chart) |
| Low Stock | All products at or below reorder level |
| Expiring Soon | Batches expiring within 30 days |

Export full stock or sales data as CSV from the Reports page.

### Stock Adjustment
**Menu:** Stock → Adjust *(Admin / Warehouse only)*

Use this only to correct counts (e.g. after a stocktake). Enter a positive number to add stock or a negative number to remove it. Always add a note explaining the reason.

---

## Role Reference

| Role | Can do |
|---|---|
| **Admin** | Everything |
| **Manager** | Dashboard, Reports, view all |
| **Warehouse** | GRN, Stock Movements, Adjustments, Dispatch |
| **WMS Operator** | GRN, Pallets, Check-In, WMS dashboard |
| **WMS Dispatcher** | Dispatch queue only |
| **Cashier** | POS Terminal, Quotes, Invoices |
| **Finance** | Dashboard, Reports |

---

## Quick Troubleshooting

| Problem | Fix |
|---|---|
| Product missing from GRN form | Edit the product → assign the Supplier |
| Can't access GRN | Role must be Admin, Warehouse, or WMS Operator |
| Stock did not increase after GRN | Check Qty Received > 0 and row not marked ✕ |
| Dispatch button grayed out | Not all lines ticked, or insufficient stock on one line |
| Invoice stock not deducted | Stock deducts at **Dispatch**, not at Invoice creation |
| Quote won't convert | Quote already converted or expired — check status |
| Low-stock alert not clearing | Resolve it manually from Alerts after restocking |
