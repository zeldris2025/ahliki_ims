# Pallet Shelving Process

How a pallet goes from the unloading area onto a shelf, and how to find it and move it afterwards, in Ah Liki IMS.

This picks up where [CONTAINER_PALLETIZING_PROCESS.md](CONTAINER_PALLETIZING_PROCESS.md) leaves off: the pallet has been built from a container line and has a printed lot label.

**Who can do this:** Admin, Manager, Warehouse Lead, WMS Operator
**Menu (WMS Operations):** 📍 **Check-In Pallet** · ↔️ **Transfer Pallet** · 📦 **Pallets** · 🗄️ **Shelf Locations**

---

## Overview

```
 🧱 Pallet built          📍 Check-In            🗄️ On shelf           ↔️ Transfer
 lot label printed  ──►   scan pallet +    ──►   location recorded  ──► (if moved later)
 ⚠ Unassigned             pick shelf             e.g. B2                 new shelf recorded,
                                                                         old one kept in history
```

Every pallet is in one of two states:

| State | Where you see it |
|---|---|
| **⚠ Unassigned**: built but not yet checked in to a shelf | 📦 **Pallets** list; the unassigned count on the 🏠 **WMS Dashboard** |
| **On a shelf**: has a current shelf location | 📦 **Pallets** list (location column); 🗄️ **Shelf Locations** under that shelf |

The goal at the end of every unload is **zero unassigned pallets**.

---

## The shelf locations

The warehouse has **78 shelf locations**, `A1` to `Z3`:

- **Letter (A–Z):** the shelf bay.
- **Number (1–3):** the level within that bay.

Each location has a QR code. To print or reprint them, go to 🗄️ **Shelf Locations** → **🖨 Print QR Codes** and stick each code on its bay and level. Scanning a shelf QR with a phone opens **Check-In Pallet** with that shelf already selected.

> Print and fix the shelf QR codes once, before the first unload. Reprint any that are damaged.

---

## Step 1 · Check the label is on the pallet

Every pallet built from a container gets a **lot number** in the form `LOT-YYYYMMDD-XXXX`, and its label has a QR code holding that number.

- If the label is missing or damaged, find the pallet in 📦 **Pallets** and click **🖨 Label** on its row to reprint it.
- Check that the product, quantity and expiry on the label match what is on the pallet.

---

## Step 2 · Choose a shelf

Put the pallet where it can be found and picked easily:

- Keep the same product together where possible. Look up where it already sits in 📦 **Pallets** (search by product name or SKU) or in 🗄️ **Shelf Locations**.
- Put short-dated stock where it is easy to reach, so it goes out first.
- Check that the shelf has physical room.

> ⚠️ The system does **not** check shelf capacity, and it allows any number of pallets on one location. Make sure the space is really free before you check a pallet in.

---

## Step 3 · Check the pallet in to the shelf

Do this **as you put the pallet down**, not at the end of the shift.

**Option A: straight from the label page (right after palletizing)**

1. After you print the label, click **📍 Check-In to Shelf** on the same page. The lot number is filled in for you.
2. Pick the **Shelf Location**, or tap a shelf button.
3. Click **📍 Check-In**.

The **📍 Check-In** button on a pallet's row in 📦 **Pallets** does the same thing.

**Option B: start from the shelf (quickest on a phone)**

1. Scan the **shelf QR code**. **Check-In Pallet → B2** opens with the shelf already selected.
2. Click **📷 Scan Pallet QR** and scan the pallet label, or type the lot number.
3. *(Optional)* Add a note, for example "Top of B2, behind LOT-…".
4. Click **📍 Check-In**.

**Option C: start from the menu**

1. Go to 📍 **Check-In Pallet**.
2. Scan the pallet label or type the lot number.
3. Pick the **Shelf Location** from the list, or tap a shelf button.
4. Click **📍 Check-In**.

**Option D: from the shelf map**

1. Go to 🗄️ **Shelf Locations**.
2. On the shelf you are filling, click **📍 Check-In to B2**, then scan the pallet.

After you save, the pallet shows as on that shelf. It appears in the shelf's **current pallets** list on the right and in **Recent Check-Ins** on the WMS Dashboard.

---

## Step 4 · Confirm nothing is left unassigned

When the container is finished:

1. Go to 📦 **Pallets** and look for any **⚠ Unassigned** pallets. You can search by product or lot number.
2. Check that the unassigned count on the 🏠 **WMS Dashboard** has gone back to what it was before this container.
3. Check in anything that was missed (Step 3).

Then close the container (see Step 6 of [CONTAINER_PALLETIZING_PROCESS.md](CONTAINER_PALLETIZING_PROCESS.md)).

---

## Moving a pallet later (Transfer)

When a pallet is moved to another shelf, the system must be updated straight away:

1. Go to ↔️ **Transfer Pallet**, or click **↔️ Transfer** on the pallet's row in 📦 **Pallets**.
2. Scan the pallet label or type the lot number. The page shows the product, quantity, expiry and **current shelf**.
3. Choose **Transfer To Shelf**.
4. *(Optional)* Add a reason, for example "Consolidating with B2".
5. Click **↔️ Transfer**.

The pallet's location history keeps the old shelf, records the move as `Transferred from <old shelf>: <note>`, and stores who moved it and when.

> Checking in a pallet that is already on a shelf also moves it. Use **Transfer** anyway, because it records where the pallet came from.

---

## Finding a pallet

| You know… | Go to |
|---|---|
| The product or SKU | 📦 **Pallets**, then search. Each pallet is listed with its shelf location and expiry. |
| The lot number | 📦 **Pallets**, then search for the lot. You can also scan it on ↔️ **Transfer Pallet** to see its current shelf. |
| The shelf | 🗄️ **Shelf Locations**: each shelf shows its current pallets and count. |

Expired pallets are flagged as **Expired dd Mmm yyyy** in the Pallets list.

---

## Correcting a pallet

If the quantity, expiry or notes on a pallet are wrong, for example after a recount:

1. In 📦 **Pallets**, click **✏️ Edit** on the pallet's row.
2. Correct the **Quantity**, **Expiry date** or **Notes**, then save.
3. The label page opens again. Reprint the label if the quantity or expiry changed.

> ⚠️ Editing a pallet changes the pallet record only. It does **not** change stock on hand. If the recount shows stock is really short or over, tell a Manager so the stock can be adjusted.

---

## Quick checklist

- [ ] Shelf QR codes are printed and fixed to every bay and level
- [ ] Every pallet has a readable lot label
- [ ] Shelf chosen: has room, same product kept together, short-dated stock easy to reach
- [ ] **📍 Check-In** done as the pallet goes onto the shelf
- [ ] No **⚠ Unassigned** pallets left from this container
- [ ] Any later move recorded with **↔️ Transfer**

---

## Troubleshooting

| Message / problem | Cause | Fix |
|---|---|---|
| *"No pallet found with lot number…"* | Mistyped lot number, or the scan misread | Rescan, or type the number exactly as printed (`LOT-YYYYMMDD-XXXX`) |
| The camera won't open on **📷 Scan Pallet QR** | The browser has blocked camera access | Allow camera access for the site in the phone's browser settings, or type the lot number |
| The shelf QR opens a login page | The phone is not signed in to the IMS | Sign in, then scan the shelf again |
| The pallet shows on the wrong shelf | It was moved without a Transfer, or checked in to the wrong shelf | Do a **↔️ Transfer** to the correct shelf |
| A pallet is still **⚠ Unassigned** after unloading | The check-in was missed | Find it on the floor by its label and do Step 3 |
| The label is lost or damaged | — | 📦 **Pallets** → **🖨 Label** on the pallet's row → print |
