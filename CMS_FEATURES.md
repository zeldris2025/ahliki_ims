# Container Management System (CMS) — Feature List

Everything available under **Container Management** (`/cms/`) in Ah Liki IMS, page by page.

---

## Navigation (on every CMS page)

Tabs across the top:

- 📊 **Dashboard**
- 🚢 **Containers**
- ⚓ **Shipping**
- ↩️ **Returned Containers**
- 🗺️ **Ah Liki Atlas**
- 📡 **Track Container** (shown as *Coming soon*, not clickable yet)

Driver names already entered elsewhere are suggested (autocomplete) in every Driver field.

---

## 1. Dashboard

**Header actions:** ⬆️ Import CSV, ➕ Add container

**Module shortcuts:** cards linking to Containers (count in yards), Shipping (owners & return days), Returned (count this month), Ah Liki Atlas, and Track Container (coming soon).

**Count tiles** (each one opens the Containers list already filtered):

| Tile | Meaning |
|---|---|
| In yards | Not yet returned |
| Full | Still loaded |
| Storage | Used for storage |
| Empty | Ready to return |
| ⚠ Overdue | Past the owner's return days (turns red when above 0) |
| ◷ Due in 7 days | To help plan trucks |

**Warning banner:** if no shipping line has return days set, a notice links to the Shipping page.

**Charts:**

- **Containers by yard:** stacked bars split into Full / Storage / Empty. Click a bar to open that yard's containers.
- **Containers by owner:** containers in yards per owner. Click a bar to filter by that owner.
- **Arrivals per week:** containers by A/Date over the last 12 weeks.
- Every chart has a **View as table** toggle.

**Return deadlines panel:** containers that are overdue or due within 14 days, most urgent first. Each row has a due badge and a one-click **Return** button. Includes a *View all* link.

**Recently returned:** latest returns with container, description, yard, status, date, staff and driver, plus a link to all returns.

---

## 2. Containers (list)

**Header actions:** ⬇️ Export CSV (exports the current filtered list), ⬆️ Import CSV, ➕ Add container

**Quick-filter tiles:** In Yards · ⚓ Wharf (not yet released) · Empty · Storage · ⚠ Overdue. The active tile is highlighted.

**Search:** across code, description, vessel, driver and note. Every word you type must match. Press `/` to jump to the search box.

**Filters panel** (⚙️ Filters, shows how many filters are active):

- Yard
- Status (Full / Storage / Empty)
- Owned (shipping line)
- Returned: *No — in yards* (default) / *Yes — returned* / *All*
- Return deadline: Overdue / Due within 7 days
- A/Date from – to
- **Clear all** resets everything

**Quick chips:** Full · ◷ Due in 7 days · ↩️ Returned · All incl. returned

**Table columns:** Container (code + short description), Yard (plus 🔁 transfer count linking to the history), Status, Owned, Vessel voyage, A/Date (with "N days ago"), Driver, Return (due badge), Note, Returned.

- **Sortable** by container, yard, status, owner and A/Date.
- Ah Liki's own (ALW) containers always sort to the end.
- Click a yard name to filter by that yard.
- Narrow screens hide the less important columns.

**Return due badges:**

| Badge | Meaning |
|---|---|
| ✓ Nd left | More than 7 days left |
| ◷ Nd left | 4–7 days left |
| ⏰ Nd left / Due today | 0–3 days left |
| ⚠ Overdue Nd | Past the deadline |
| — No deadline | No A/Date, or the owner has no return days set |
| Returned | Already returned |

**Row actions:** 🔁 Transfer · Edit · Return

**Bulk actions** (tick rows, or tick the header box to select the whole page; a bar appears at the bottom):

- Move to yard
- Set status
- ↩️ Return… (opens a dialog for date, staff and driver)
- Delete (asks to confirm)
- ✕ Clear selection

**Pagination:** 50 per page, with "Showing X–Y of Z".

---

## 3. Add / Edit Container

**Fields:**

| Field | Required | Notes |
|---|---|---|
| Code | Yes | Normalised automatically. Blocked if the same code is already in a yard. |
| Description | No | |
| Yard | Yes | |
| Status | Yes | Full, Storage or Empty |
| Owner | Yes | Shipping line |
| Vessel voyage | No | |
| A/Date | No | Arrival date |
| Driver | No | Suggests known drivers |
| Note | No | |

- Choosing the **Wharf** yard automatically adds "NOT YET RELEASED" to the note. The server does the same when saving.
- **Save & add another** (when adding) keeps the same yard selected.
- When adding, a **Tips** panel explains return deadlines, CSV import and *Save & add another*.

**When editing an existing container:**

- The header shows the code, status, due badge, yard, owner, arrival date and delivering driver.
- **🔁 Transfer** and **↩️ Return to wharf** buttons (hidden once the container is returned).
- **Return to wharf panel:**
  - If returned: shows the date, the yard it came from, status, staff and driver, with an **Undo return** button.
  - If not returned: shows the due date and how it was worked out, or explains why there is no deadline yet.
- **Transfer history:** every move between yards, newest first, with date, driver, staff and reason. The latest move is tagged *Current*, and the first yard is shown at the bottom.
- **Earlier visits:** past visits of the same container code, with A/Date, yard, driver and returned date.
- **Audit info:** who added it and when, and when it was last updated.
- **🗑 Delete container** (asks to confirm; its return history is deleted too).

---

## 4. Transfer dialog

Moves a container to another yard. Fields:

- From (fixed to the current yard)
- To (the current yard is hidden from the list)
- Date
- Driver
- Staff name
- Reason (optional)

Every transfer is saved to the container's history. Transferring to the Wharf adds the "NOT YET RELEASED" note.

---

## 5. Return dialog

Records a container as returned. Location is always set to **Wharf**.

- Fields: Returned date (defaults to today), Staff name (pre-filled with the logged-in user), Driver.
- Close it with Esc or by clicking outside the dialog.

---

## 6. Import CSV

A three-step flow: **Download template → Upload & check → Confirm**.

- ⬇️ **Download template** gives a CSV with the correct headers and sample rows.
- Drag-and-drop or click to upload. Maximum 5 MB.
- Saving from Excel as "CSV UTF-8" is supported.
- **Columns:** Container Code, Description, Yard, Status, Owned, Vessel Voyage, A/Date, Driver, Note, Returned.
  - Required: Container Code, Yard, Status, Owned
  - Status: FULL, STORAGE or EMPTY
  - A/Date: DD/MM/YYYY (also accepts 2026-10-03 and 3-Oct-26)
  - Returned: Yes or No (blank = No)
- The upload panel lists valid yard and owner names, with a link to add owners.
- **Preview before saving:** shows counts for new containers, updates, rows marked returned and rows with errors.
- Rows with errors are listed with line number and problem, and are skipped.
- A preview table marks each row **New** or **Update**. A container code already in a yard is updated, not duplicated.
- **✓ Import N rows** confirms the import. *Choose another file* starts over.

---

## 7. Shipping (owners & return days)

- A table of shipping lines showing:
  - Name
  - Return days (or *Not set*)
  - Containers in yards
  - Overdue count
  - Due ≤ 7 days count
- Each count links to the matching filtered Containers list.
- Add or edit a shipping line (name and return days):
  - Names are stored in upper case.
  - Duplicate names are blocked.
- Delete is only offered for lines with no containers.
- Changing return days updates every deadline immediately. Return due = A/Date + return days.

---

## 8. Returned Containers

- **Count tiles:** last 7 days, this month, all time.
- **Search** across container, description, staff and driver.
- **Filters:** yard, status, returned-date range, and Clear.
- **⬇️ Export CSV** of the filtered list.
- **Table columns:** Container (links to its page), Description, Yard it came from, Status, Location (⚓ Wharf), Returned date, Staff, Driver.
- **Undo** a return (asks to confirm). This puts the container back in its yard.
- 50 per page.

---

## 9. Ah Liki Atlas (map)

An interactive map of Upolu showing every yard.

**Map:**

- Street and satellite base layers.
- **Apia area** and **Whole Upolu** zoom buttons.
- Yard pins:
  - Show the container count.
  - Grow with the count.
  - Show a red **!** when the yard has overdue containers.
  - Turn grey when the yard is empty.
  - The Wharf has its own colour.
- **Hover a pin** (or a yard in the side list) for a summary card:
  - Total containers, with a Full / Storage / Empty bar.
  - Containers per owner.
  - Overdue and due-within-7-days warnings.
- **Click a pin** to open that yard in the side panel.
- **📍 Adjust pins** mode: drag pins to their real position. Each move saves automatically. Click **✓ Done** to finish.

**Side panel:**

- **All yards overview:**
  - Total containers and overdue count.
  - Yards sorted by number of containers, each with a status bar.
- **Status filter chips:** All / Full / Storage / Empty. These update both the pins and the lists.
- **Yard view:** the containers in that yard, each showing status, owner, arrival date, driver and due badge, with links to:
  - **Open in Containers →**
  - **➕ Add here**
  - Each container's edit page
- **Search** across container, yard, owner, driver, description and vessel:
  - Results are grouped into *Yards* and *Containers*, with matches highlighted.
  - Up to 150 results are shown.
  - Pins that don't match are dimmed.
  - Enter jumps straight to a single match. Esc clears the search. `/` focuses the search box.
- The selected yard is kept in the URL (`?yard=ID`), so links can open straight to that yard.

---

## Coming soon

- 📡 **Track Container:** shown in the tabs and on the dashboard but not yet available.
