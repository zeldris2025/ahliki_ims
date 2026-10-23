# Container Arrival & Palletizing Process

How the warehouse receives a container at HQ, unloads it onto pallets, shelves the pallets, and closes the container in Ah Liki IMS.

**Who can do this:** Admin, Manager, Warehouse Lead, WMS Operator
**Menu:** Sidebar → 🚢 **Containers** (warehouse view) and 📍 **Check-In Pallet**

---

## Overview

```
 🏢 AT HQ (HQ-ALW-VAI) ──► 📋 LIST ADDED ──► 📂 OPENED ──► 🧱 PALLETIZED ──► 🔒 CLOSED
   from the CMS yard        Step 1           Step 2        Steps 3–4         Step 6
                            (Inventory)      GRN + stock   automatic once    CMS box set
                                             raised here   every unit is     to Empty
                                                           on a pallet
```

| Stage | Meaning | Who moves it on |
|---|---|---|
| At HQ, waiting for the list | The container is in the HQ-ALW-VAI yard in the CMS, but nobody has entered its contents yet | Inventory — **➕ Add list** |
| At HQ, list added | The products and quantities are in; ready to unload | Warehouse — **📂 Open** |
| Opened | Doors open, GRN raised, stock on hand; unloading in progress | Warehouse — **Palletize** each line |
| Palletized | Every unit on the list is on a pallet | Set automatically by the system |
| Closed | Container emptied and signed off; the CMS container becomes **Empty** | Warehouse — **Close Container** |

---

## Before you start

- The container must be recorded in the CMS at yard **HQ-ALW-VAI**. Every container there shows in the **🏢 At HQ** tab, except Ah Liki's own boxes (owner **ALW**) and boxes already marked Empty.
- Check that the container number on the box matches the number in the system.
- Have the label printer ready and the pallet QR scanner (or a phone) to hand.

---

## Step 1 · Inventory adds the list

A container with no contents entered shows **⏳ Waiting for Inventory to add the list**, and it can't be opened yet.

**Inventory** (Admin, Manager or Warehouse Lead):

1. Go to **🚢 Containers** → **🏢 At HQ**.
2. Click **➕ Add list** on the container. The container number, vessel and arrival date are filled in from the CMS.
3. Pick the **Supplier**. It is needed for the GRN.
4. Add one line per product: **product**, **quantity** and *(optional)* **expiry date**.
5. Save.

The row then shows the number of lines and an **📂 Open** button. The list can still be corrected (**View** → **✏️ Edit manifest**) until the container is opened. After that it is locked.

---

## Step 2 · Open the container

When you are ready to unload:

1. In **🏢 At HQ**, click **📂 Open** on the container and confirm. You can also click **📂 Open Container** on the container's page.

When you confirm, the system:

- Raises a **GRN** automatically (`GRN-YYYYMMDD-NNNN`) for the container's supplier.
- Creates one GRN line per manifest line, each with its own batch number (`BTH-YYYYMMDD-NNNN`) and the manifest expiry date.
- Puts the **full manifest quantity on hand as stock** (a stock-in movement referencing the GRN).
- Runs the low-stock / expiry alert checks for each product.
- Sets the status to **Opened**.

> ⚠️ Opening adds stock straight away, so open the container only once it is physically at HQ and you are about to unload it. A container that has no manifest lines cannot be opened.

---

## Step 3 · Palletize each manifest line

Work through the manifest lines as you unload. For each product:

1. On the container page, click **🧱 Palletize** next to the line.
2. Fill in the pallet form:

| Field | What to enter |
|---|---|
| **Quantity on this pallet** | Units physically placed on this pallet. Defaults to everything still left on the line. |
| **Expiry date** *(optional)* | Defaults to the manifest expiry. Change it if the stock on this pallet has a different date. |
| **Notes** *(optional)* | Anything worth recording, such as the pallet condition or a mixed-batch note. |

3. Save. The system creates the pallet with a unique **lot number** (`LOT-YYYYMMDD-XXXX`), linked to the container line and its GRN line.
4. The **pallet label** opens. Click **🖨 Print Label** and stick it on the pallet. The QR code holds the lot number.

**One line, several pallets:** if a product doesn't fit on one pallet, enter a smaller quantity and save. Click **🧱 Palletize** on the same line again for the next pallet. The form shows how many units are still left (e.g. *"120 of 400 still to palletize"*).

**Rules the system enforces:**

- You cannot palletize until the container has been opened.
- A pallet can never hold more than the quantity still left on its line.
- A line that is fully palletized no longer offers **Palletize**.

---

## Step 4 · Check each pallet in to a shelf

Put every labelled pallet away and record where it went:

1. Go to **📍 Check-In Pallet**.
2. Click **📷 Scan Pallet QR Code** and scan the label, or type the lot number.
3. Choose the **shelf location** (e.g. `A1`, `B3`). Scanning the shelf's QR code fills this in for you.
4. Save. The pallet now shows at that shelf, and the shelf's current pallets are listed on the right.

> Checking in a pallet that is already on a shelf moves it to the new location. The previous location is kept in the pallet's history.

---

## Step 5 · Report damage or shortages

If goods are damaged, broken or missing while unloading:

1. On the container page, go to **Comments & Damage Reports**.
2. Describe the problem: the product, the quantity, and what happened.
3. Tick **Damage report** so the comment is flagged.

You can add comments at any time until the container is closed.

---

## Step 6 · Close the container

When the **last unit has been palletized**, the status changes to **🧱 Palletized** by itself. Then:

1. Click **Close Container**.
2. *(Optional)* Add a closing comment. Tick **Damage report** if it describes damage.
3. Confirm.

The status changes to **Closed**, and the system records who closed it and when. No more pallets or comments can be added. The container's CMS status changes to **Empty**, so the broker can see it is ready to go back to the wharf.

> If units are still left to palletize, the system blocks the close and tells you how many units remain.

---

## Quick checklist

- [ ] Container number on the box matches the system
- [ ] Inventory has used **➕ Add list** to enter the contents
- [ ] **📂 Open Container**: GRN raised, stock on hand
- [ ] **🧱 Palletize** every manifest line, one pallet at a time
- [ ] **🖨 Print Label** and attach it to every pallet
- [ ] **📍 Check-In Pallet** to a shelf for every pallet
- [ ] Damage or shortages recorded as a **Damage report**
- [ ] Status shows **🧱 Palletized**
- [ ] **Close Container**

---

## Troubleshooting

| Message / problem | Cause | Fix |
|---|---|---|
| *"Open the container before palletizing its contents."* | The container hasn't been opened yet | Complete Steps 1–2 first |
| The container isn't in the **At HQ** tab | It isn't at yard HQ-ALW-VAI in the CMS, is owned by ALW, or is already marked Empty | Check its yard, owner and status in the CMS |
| *"Only N left to palletize on this line."* | The pallet quantity is more than what's left on the line | Enter N or fewer |
| *"…is already fully palletized."* | Every unit on that line is already on a pallet | Move on to the next line |
| *"…still has N unit(s) to palletize before it can be closed."* | Some lines are not finished | Palletize the remaining units, then close |
| **⏳ Waiting for Inventory to add the list** | No contents have been entered yet | Ask Inventory to click **➕ Add list** |
| *"No pallet found with lot number…"* (shelf check-in) | Mistyped lot number or a misread scan | Rescan the label or check the lot number on the label |
| Manifest quantity doesn't match what came out of the box | A shortage or overage at the supplier | Record the difference in a **Damage report** comment and tell a Manager. Stock was booked at the manifest quantity when the container was opened, so a short line needs a stock adjustment. The container can't be closed until the full manifest quantity is palletized, so a Manager has to decide how to clear the short units. |
