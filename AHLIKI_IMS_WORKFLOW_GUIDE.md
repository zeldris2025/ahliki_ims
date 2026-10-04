# AHLIKI IMS QUICK WORKFLOW DIAGRAMS

This document provides visual workflows for each user role.

---

## ADMIN WORKFLOW

```
┌─────────────────────────────────────────────────────────┐
│                   ADMIN WORKFLOWS                        │
└─────────────────────────────────────────────────────────┘

WORKFLOW 1: SYSTEM SETUP (First Time)
═════════════════════════════════════

    START
      │
      ├─→ Create User Accounts
      │   └─→ Set Username, Password, Role
      │       └─→ Users can log in
      │
      ├─→ Create Categories
      │   └─→ Electronics, Food, etc.
      │       └─→ Used for product organization
      │
      ├─→ Create Suppliers
      │   └─→ Enter supplier details
      │       └─→ Used for purchase orders
      │
      └─→ Create Products
          └─→ SKU, Name, Price, Category
              └─→ Ready for sales/receiving


WORKFLOW 2: DAILY OPERATIONS
════════════════════════════

    LOGIN
      │
      ├─→ VIEW DASHBOARD
      │   │
      │   ├─→ Check Low Stock Products
      │   ├─→ Check Open Alerts
      │   ├─→ Review Today's Sales
      │   └─→ Monitor Stock Value
      │
      ├─→ MANAGE SYSTEM
      │   │
      │   ├─→ Add/Edit Products
      │   ├─→ Monitor Users
      │   ├─→ Review Activities
      │   └─→ Manage Alerts
      │
      └─→ OVERSIGHT
          │
          ├─→ Financial Review
          ├─→ Stock Levels
          └─→ System Maintenance


WORKFLOW 3: EMERGENCY PROCEDURES
════════════════════════════════

    ISSUE DETECTED
      │
      ├─→ [IF Low Stock]
      │   └─→ Alert Warehouse
      │       └─→ Create PO
      │
      ├─→ [IF Stock Discrepancy]
      │   └─→ Alert Finance
      │       └─→ Initiate Audit
      │
      ├─→ [IF System Error]
      │   └─→ Contact IT
      │       └─→ Document Issue
      │
      └─→ [IF User Issue]
          └─→ Reset Password / Permissions
              └─→ User Back Online
```

---

## FINANCE WORKFLOW

```
┌─────────────────────────────────────────────────────────┐
│                  FINANCE WORKFLOWS                       │
└─────────────────────────────────────────────────────────┘

WORKFLOW 1: DAILY SALES MONITORING
═════════════════════════════════

    LOGIN → DASHBOARD
      │
      ├─→ Check Daily Sales Total
      │   └─→ Compare to Target
      │
      ├─→ Review Sales by Payment
      │   ├─→ Cash Sales
      │   ├─→ Credit Sales
      │   └─→ EFTPOS Sales
      │
      ├─→ Verify Totals Match Till
      │   └─→ Investigate Variances
      │
      └─→ Report to Management


WORKFLOW 2: CUSTOMER CREDIT MANAGEMENT
═══════════════════════════════════════

    CUSTOMER PURCHASE
      │
      ├─→ CREATE INVOICE
      │   ├─→ Enter Customer Name
      │   ├─→ Enter Account Number
      │   └─→ Add Line Items
      │
      ├─→ TRACK PAYMENT
      │   ├─→ Unpaid → Follow up
      │   ├─→ Overdue → Priority
      │   └─→ Paid → Close
      │
      └─→ UPDATE RECORDS


WORKFLOW 3: QUOTE TO INVOICE
════════════════════════════

    CUSTOMER REQUEST
      │
      ├─→ CREATE QUOTE
      │   ├─→ Customer Name
      │   ├─→ Add Products
      │   └─→ System Calculates Total
      │
      ├─→ CUSTOMER REVIEWS
      │   ├─→ [IF Rejects] → End
      │   └─→ [IF Accepts] → Convert
      │
      ├─→ CONVERT TO INVOICE
      │   └─→ System Creates Invoice
      │
      └─→ READY FOR DELIVERY & PAYMENT


WORKFLOW 4: FINANCIAL REPORTING
═══════════════════════════════

    END OF PERIOD
      │
      ├─→ GENERATE SALES REPORT
      │   ├─→ Set Date Range
      │   ├─→ Review Totals
      │   └─→ Export to CSV
      │
      ├─→ GENERATE STOCK REPORT
      │   ├─→ Current Stock Qty
      │   ├─→ Stock Value
      │   └─→ Export for Audit
      │
      ├─→ ANALYZE PROFITABILITY
      │   ├─→ Margin per Product
      │   ├─→ Margin %
      │   └─→ Compare to Target
      │
      └─→ FINANCIAL STATEMENTS
          ├─→ Revenue Summary
          ├─→ Cost Analysis
          └─→ Submit to Management
```

---

## CUSTOMS BROKER WORKFLOW

```
┌─────────────────────────────────────────────────────────┐
│              CUSTOMS BROKER WORKFLOW                     │
└─────────────────────────────────────────────────────────┘

WORKFLOW: LODGING A CONTAINER AT THE WHARF
══════════════════════════════════════════

    CONTAINER LANDS AT THE WHARF
      │
      ├─→ OPEN "Containers → New Container"
      │
      ├─→ RECORD THE CONTAINER
      │   ├─→ Container Number  (e.g. MSKU1234567)
      │   ├─→ Supplier          (required — the GRN is raised against it)
      │   ├─→ Vessel / Voyage   (optional)
      │   ├─→ B/L Number        (optional)
      │   └─→ Wharf Arrival Date
      │
      ├─→ RECORD THE CONTENTS (one line per item)
      │   ├─→ Item / Product
      │   ├─→ Quantity
      │   ├─→ Expiry Date  ← OPTIONAL, blank for non-perishables
      │   └─→ Notes        ← OPTIONAL
      │
      ├─→ SAVE  →  Status: 🚢 AT WHARF
      │
      └─→ [Manifest can still be edited until the warehouse OPENS it]

    The container now appears in the warehouse "Containers" tab,
    waiting to be checked in.
```

---

## CONTAINER WORKFLOW (WHARF → HQ → SHELF)

```
┌─────────────────────────────────────────────────────────┐
│      END-TO-END CONTAINER FLOW ACROSS BOTH ROLES        │
└─────────────────────────────────────────────────────────┘

  CUSTOMS BROKER                 WAREHOUSE / WMS
  ──────────────                 ───────────────

  1. Lodge container
     + full manifest
     │
     └─→ 🚢 AT WHARF ──────────→ 2. Warehouse → Containers
                                     "Awaiting Check-In" tab
                                     │
                                     └─→ [ 📥 CHECK IN ]
                                            │
                                            ▼
                                     🏢 CHECKED IN AT HQ
                                     (who + when recorded)
                                            │
                                     3. Click the container,
                                        then [ 📂 OPEN ]
                                            │
                                            ├─→ GRN auto-generated ✓
                                            ├─→ Batch numbers assigned ✓
                                            ├─→ STOCK GOES ON HAND ✓
                                            └─→ Expiry alerts checked ✓
                                            │
                                            ▼
                                     📂 OPENED
                                            │
                                     4. Palletize each line
                                        [ 🧱 PALLETIZE ]
                                        ├─→ Choose quantity
                                        │   (a line can be split
                                        │    across several pallets)
                                        ├─→ Lot number generated ✓
                                        └─→ Print pallet label
                                            │
                                            ▼
                                     5. Check pallet in to a shelf
                                        (existing WMS Check-In flow)
                                            │
                                     [when every unit is palletized]
                                            ▼
                                     🧱 PALLETIZED
                                            │
                                     6. Add comments / damage reports
                                        ⚠️ Flag broken or short goods
                                            │
                                     7. [ 🔒 CLOSE CONTAINER ]
                                        (optional closing note)
                                            │
                                            ▼
                                     ✅ CLOSED
                                        Comments locked


RULES ENFORCED BY THE SYSTEM
════════════════════════════

  • The broker may only amend a manifest while the container is
    AT WHARF or CHECKED IN — never after it is opened.
  • A container cannot be palletized until it has been opened.
  • A pallet can never exceed the quantity left on its manifest line.
  • A container cannot be CLOSED until every unit is palletized.
  • Once CLOSED, no further comments can be added.
  • Opening a container twice will not duplicate its GRN or stock.
```

---

## WAREHOUSE WORKFLOW

```
┌─────────────────────────────────────────────────────────┐
│                 WAREHOUSE WORKFLOWS                      │
└─────────────────────────────────────────────────────────┘

WORKFLOW 1: RECEIVING GOODS FROM SUPPLIER
═════════════════════════════════════════

    GOODS ARRIVE AT WAREHOUSE
      │
      ├─→ PREPARE
      │   ├─→ Verify Purchase Order
      │   ├─→ Prepare Receiving Area
      │   └─→ Gather Documents
      │
      ├─→ RECEIVE (Physical Action)
      │   ├─→ Count Items
      │   ├─→ Inspect Quality
      │   └─→ Check Batch/Expiry
      │
      ├─→ RECORD GRN
      │   ├─→ Select Supplier
      │   ├─→ Add Each Item
      │   │   ├─→ Product
      │   │   ├─→ Quantity
      │   │   ├─→ Batch Number
      │   │   └─→ Expiry Date
      │   └─→ Save GRN
      │
      ├─→ SYSTEM ACTIONS
      │   ├─→ Stock Increased ✓
      │   ├─→ GRN Number Generated ✓
      │   ├─→ Alerts Created (if needed) ✓
      │   └─→ Movement Recorded ✓
      │
      ├─→ [IF Discrepancy Detected]
      │   ├─→ Document Variance
      │   ├─→ Alert Admin/Finance
      │   └─→ Contact Supplier
      │
      └─→ STOCK AVAILABLE FOR SALE


WORKFLOW 2: MONITORING STOCK LEVELS
═══════════════════════════════════

    DURING DAY
      │
      ├─→ VIEW CURRENT STOCK
      │   ├─→ Product → Details
      │   ├─→ Check Current Level
      │   └─→ Compare to Reorder Level
      │
      ├─→ [IF Low Stock Alert]
      │   ├─→ Note Product
      │   └─→ Report to Admin
      │
      ├─→ [IF Expiry Warning]
      │   ├─→ Note Batch
      │   ├─→ Mark for Priority Sale
      │   └─→ Resolve Alert
      │
      └─→ [IF Normal]
          └─→ Continue Operations


WORKFLOW 3: STOCK ADJUSTMENTS
═════════════════════════════

    DISCREPANCY FOUND
      │
      ├─→ [IF Damage]
      │   ├─→ Remove from Shelf
      │   ├─→ Create Adjustment
      │   │   ├─→ Quantity: -1 (or amount)
      │   │   ├─→ Reason: Damage
      │   │   └─→ Note: Details
      │   └─→ Save
      │
      ├─→ [IF Loss/Theft]
      │   ├─→ Document Finding
      │   ├─→ Create Adjustment
      │   │   ├─→ Negative Quantity
      │   │   ├─→ Reason: Loss/Theft
      │   │   └─→ Note: Circumstances
      │   └─→ Alert Management
      │
      ├─→ [IF Physical Count Variance]
      │   ├─→ Record Discrepancy
      │   ├─→ Create Adjustment
      │   │   ├─→ Actual - System = Adjustment
      │   │   └─→ Note: Audit
      │   └─→ Update Records
      │
      └─→ SYSTEM UPDATED ✓


WORKFLOW 4: INVENTORY AUDIT
═══════════════════════════

    AUDIT SCHEDULED
      │
      ├─→ PREPARATION
      │   ├─→ Print Current Stock
      │   ├─→ Divide Warehouse
      │   └─→ Prepare Count Sheets
      │
      ├─→ PHYSICAL COUNT
      │   ├─→ Zone 1: Count All Items
      │   ├─→ Zone 2: Count All Items
      │   ├─→ Zone 3: Count All Items
      │   └─→ Record Actual Qty
      │
      ├─→ COMPARISON
      │   ├─→ Actual vs System
      │   ├─→ Identify Variances
      │   └─→ Investigate Large Gaps
      │
      ├─→ RECORDING ADJUSTMENTS
      │   ├─→ For Each Variance
      │   │   ├─→ Stock → Adjust
      │   │   ├─→ Enter Quantity
      │   │   └─→ Reason: Physical Audit
      │   └─→ Save All
      │
      └─→ AUDIT COMPLETE ✓
          System Now Matches Physical


WORKFLOW 5: ALERTS MANAGEMENT
═════════════════════════════

    ALERT TRIGGERED
      │
      ├─→ [LOW STOCK]
      │   ├─→ View Alert
      │   ├─→ Note Current Level
      │   ├─→ Report to Admin
      │   ├─→ Wait for PO
      │   └─→ Resolve When Received
      │
      ├─→ [EXPIRY WARNING]
      │   ├─→ View Alert
      │   ├─→ Note Batch & Date
      │   ├─→ Mark for Priority
      │   ├─→ Or Prepare Disposal
      │   └─→ Resolve When Handled
      │
      └─→ [DISCREPANCY]
          ├─→ View Alert
          ├─→ Contact Supplier
          ├─→ Document Resolution
          └─→ Resolve Alert
```

---

## CASHIER WORKFLOW

```
┌─────────────────────────────────────────────────────────┐
│                   CASHIER WORKFLOWS                     │
└─────────────────────────────────────────────────────────┘

WORKFLOW 1: PROCESS CASH SALE
════════════════════════════

    CUSTOMER ARRIVES AT COUNTER
      │
      ├─→ POS LOGIN
      │   └─→ Enter Credentials
      │
      ├─→ ADD ITEMS TO CART
      │   ├─→ Scan Item Barcode (or enter SKU)
      │   │   └─→ Product Appears
      │   ├─→ Enter Quantity
      │   ├─→ Click Add to Sale
      │   └─→ Repeat for Each Item
      │
      ├─→ REVIEW CART
      │   ├─→ Check All Items Correct
      │   ├─→ Verify Quantities
      │   ├─→ Check Unit Prices
      │   └─→ Review Subtotal
      │
      ├─→ CHECKOUT
      │   ├─→ Click Checkout Button
      │   ├─→ Select: CASH
      │   ├─→ Enter Amount Tendered
      │   └─→ System Calculates Change
      │
      ├─→ COMPLETE SALE
      │   ├─→ Click Complete
      │   ├─→ Receipt Prints
      │   ├─→ Sale Number Generated
      │   └─→ Stock Updated
      │
      ├─→ PROVIDE TO CUSTOMER
      │   ├─→ Bag Items
      │   ├─→ Give Receipt
      │   ├─→ Return Change
      │   └─→ Thank You!
      │
      └─→ NEW SALE READY
          Repeat for Next Customer


WORKFLOW 2: PROCESS CREDIT ACCOUNT SALE
═════════════════════════════════════════

    CUSTOMER: "I Have a BC Account"
      │
      ├─→ ADD ITEMS TO CART (Same as Cash)
      │   ├─→ Scan Barcodes
      │   ├─→ Enter Quantities
      │   └─→ Review Items
      │
      ├─→ CHECKOUT
      │   ├─→ Click Checkout
      │   ├─→ Select: CREDIT ACCOUNT
      │   └─→ Enter Account Number
      │
      ├─→ VERIFY ACCOUNT
      │   ├─→ System Shows Account Holder
      │   ├─→ Confirm Correct Person
      │   └─→ Approved? YES → Continue
      │
      ├─→ COMPLETE
      │   ├─→ Click Complete
      │   ├─→ Invoice Created
      │   └─→ Receipt Prints
      │
      ├─→ PROVIDE TO CUSTOMER
      │   ├─→ Receipt Copy
      │   └─→ "Invoice will be mailed"
      │
      └─→ FINANCE TRACKS PAYMENT
          Invoice Added to Customer Account


WORKFLOW 3: PROCESS CARD (EFTPOS) SALE
══════════════════════════════════════

    CUSTOMER: "Paying by Card"
      │
      ├─→ ADD ITEMS TO CART (Same)
      │   └─→ Scan & Quantities
      │
      ├─→ CHECKOUT
      │   ├─→ Click Checkout
      │   ├─→ Select: EFTPOS
      │   └─→ Confirm Total Amount
      │
      ├─→ CARD PAYMENT
      │   ├─→ "Please Insert/Tap Card"
      │   ├─→ Customer Inserts Card
      │   ├─→ Customer Enters PIN
      │   └─→ EFTPOS Processing...
      │
      ├─→ VERIFICATION
      │   ├─→ [IF Approved] ✓
      │   │   ├─→ Continue
      │   │   └─→ Mark Sale Complete
      │   │
      │   └─→ [IF Declined] ✗
      │       ├─→ "Card Declined"
      │       ├─→ Try Different Card
      │       └─→ Or Cancel Sale
      │
      ├─→ COMPLETE
      │   ├─→ Click Complete
      │   ├─→ Receipt Prints (2 copies)
      │   └─→ Sale Recorded
      │
      └─→ CUSTOMER SIGNS/LEAVES
          With Receipt & Card


WORKFLOW 4: TILL RECONCILIATION
═══════════════════════════════

    END OF SHIFT
      │
      ├─→ STOP ACCEPTING SALES
      │   └─→ End active transaction
      │
      ├─→ CASH COUNT
      │   ├─→ Remove Cash from Till
      │   ├─→ Count Carefully
      │   ├─→ Record Actual Amount
      │   └─→ Recount if Unsure
      │
      ├─→ SYSTEM RECONCILIATION
      │   ├─→ Click Till Reconciliation
      │   ├─→ System Shows Expected Total
      │   ├─→ Enter Actual Count
      │   └─→ System Calculates Variance
      │
      ├─→ VARIANCE CHECK
      │   ├─→ [IF Matches] ✓
      │   │   └─→ Perfect! Click Confirm
      │   │
      │   └─→ [IF Variance] ⚠️
      │       ├─→ Investigate Causes
      │       ├─→ Check for:
      │       │   ├─→ Discounts Applied
      │       │   ├─→ Returns Made
      │       │   ├─→ Voids
      │       │   └─→ Math Errors
      │       ├─→ Recount if Large
      │       └─→ Report to Manager
      │
      ├─→ FINALIZE
      │   ├─→ Click Confirm
      │   ├─→ Manager Reviews
      │   └─→ Shift Closed
      │
      └─→ OFF DUTY
          Come Back Tomorrow!


WORKFLOW 5: HANDLE RETURNS
══════════════════════════

    CUSTOMER: "I Want to Return This"
      │
      ├─→ VERIFY RETURN ELIGIBILITY
      │   ├─→ Check Receipt Date
      │   ├─→ Within Return Window? YES
      │   ├─→ Item in Good Condition? YES
      │   └─→ [If NO to any] → Cannot Return
      │
      ├─→ PROCESS RETURN
      │   ├─→ Click Process Return
      │   ├─→ Enter Sale Number (from receipt)
      │   ├─→ Select Item to Return
      │   ├─→ Enter Return Quantity
      │   ├─→ Select Reason
      │   │   ├─→ Defective
      │   │   ├─→ Changed Mind
      │   │   └─→ Damaged
      │   └─→ Click Process
      │
      ├─→ REFUND APPLIED
      │   ├─→ Original Payment Method
      │   ├─→ Amount Credited
      │   └─→ Confirmation Printed
      │
      ├─→ STOCK UPDATED
      │   └─→ Returned Item Added Back
      │
      └─→ CUSTOMER SATISFIED
          Thank You & Goodbye!


WORKFLOW 6: HANDLE ISSUES
═════════════════════════

    PROBLEM AT POS
      │
      ├─→ [Product Not Found]
      │   ├─→ Clean Barcode
      │   ├─→ Try Scan Again
      │   ├─→ Manual Search by Name
      │   └─→ If Still Not There
      │       ├─→ Call Manager
      │       └─→ Ring Item Manually
      │
      ├─→ [Insufficient Stock]
      │   ├─→ POS Shows Warning
      │   ├─→ Inform Customer
      │   ├─→ Sell Available Amount
      │   └─→ Alert Warehouse
      │
      ├─→ [Card Declined]
      │   ├─→ Try Card Again
      │   ├─→ Check Expiry Date
      │   ├─→ Try Different Card
      │   └─→ Or Switch to Cash
      │
      ├─→ [System Slow]
      │   ├─→ Wait 10 Seconds
      │   ├─→ Refresh Page
      │   ├─→ Restart POS
      │   └─→ Call IT if Continues
      │
      └─→ [Need Manager Approval]
          ├─→ Discount Request
          ├─→ Return Request
          └─→ Special Price
              └─→ Call Manager to Counter
```

---

## ROLE INTERACTION MAP

```
┌────────────────────────────────────────────────────────┐
│         HOW ROLES INTERACT WITH EACH OTHER             │
└────────────────────────────────────────────────────────┘


SCENARIO 1: CUSTOMER PURCHASE TO PAYMENT
════════════════════════════════════════

    CASHIER                      WAREHOUSE              FINANCE
    ───────                      ─────────              ───────
    
    Customer Arrives
         │
         ├─→ Scan Items
         │   └─→ Stock Checked ◄─── Provided by
         │
         ├─→ Complete Sale
         │   └─→ Stock Decreased ◄─── Updated by
         │
         ├─→ [If Credit]
         │   └─→ Invoice Created ──→ Finance Tracks
         │                              │
         │                              ├─→ Follow Up
         │                              └─→ Record Payment
         │
         └─→ [If Cash]
             └─→ Cash to Till
                 └─→ Reconciled at Shift End


SCENARIO 2: SUPPLIER DELIVERY
═════════════════════════════

    ADMIN                    WAREHOUSE               FINANCE
    ────                     ─────────               ───────
    
    Creates PO
         │
         ├─→ Notifies Warehouse ──→ Prepares to Receive
         │                              │
         │                              ├─→ Goods Arrive
         │                              ├─→ Count & Inspect
         │                              ├─→ Record GRN
         │                              ├─→ Stock Increased
         │                              └─→ Alerts Created
         │
         ├─→ Alerts Check ◄─────────────┤
         │                              │
         └─→ [If Discrepancy] ────→ Finance Contacted
                                        │
                                        ├─→ Check Invoice
                                        ├─→ Verify Cost
                                        └─→ Process Payment


SCENARIO 3: LOW STOCK ALERT
═══════════════════════════

    WAREHOUSE          ADMIN              FINANCE
    ─────────          ─────              ───────
    
    Detects Low Stock
         │
         ├─→ Alert Created
         │   └─→ Notifies Admin
         │
    Admin Reviews
         │
         ├─→ [Decision: Order More]
         │   └─→ Creates PO
         │       └─→ Sends to Warehouse
         │
         └─→ Finance Monitors
             ├─→ Budget Available?
             ├─→ Approve Cost?
             └─→ Track Inventory Value


SCENARIO 4: INVENTORY AUDIT
═══════════════════════════

    WAREHOUSE           ADMIN              FINANCE
    ─────────           ─────              ───────
    
    Physical Count
         │
         ├─→ Compare to System
         │   └─→ Variances Found
         │
    Record Adjustments
         │
         ├─→ Admin Reviewed
         │   └─→ Approves/Investigates
         │
         └─→ Finance Updated
             ├─→ Stock Value Changed
             └─→ Accounting Records
```

---

## QUICK STATUS INDICATORS

```
┌────────────────────────────────────────────────────────┐
│          SYSTEM STATUS & WHAT THEY MEAN                │
└────────────────────────────────────────────────────────┘

PRODUCT STATUS
══════════════

✅ Active (Green)
   └─→ Product can be sold
   └─→ Receives and shows stock

❌ Inactive (Gray)
   └─→ Product not for sale
   └─→ Hidden from POS
   └─→ Still in system for history


STOCK LEVELS
════════════

🟢 GREEN (Good Stock)
   └─→ Stock Above Reorder Level
   └─→ Normal Operations
   └─→ No Action Needed

🟠 ORANGE (Low Stock)
   └─→ Stock Below Reorder Level
   └─→ Alert Generated
   └─→ Action: Order from Supplier

🔴 RED (Critical)
   └─→ Stock Very Low or Zero
   └─→ Priority Alert
   └─→ Action: Emergency Reorder


INVOICE STATUS
══════════════

📋 Unpaid
   └─→ Invoice Created
   └─→ Waiting for Payment
   └─→ Action: Follow Up

✓ Paid
   └─→ Payment Received
   └─→ Closed
   └─→ No Action

⏰ Overdue
   └─→ Payment Date Passed
   └─→ Priority Follow Up
   └─→ Action: Contact Customer


QUOTE STATUS
════════════

📝 Active
   └─→ Quote Valid
   └─→ Awaiting Customer Decision
   └─→ Can Still Convert

✓ Converted
   └─→ Quote Accepted by Customer
   └─→ Converted to Invoice
   └─→ Ready for Delivery

❌ Expired
   └─→ Quote Past Valid Date
   └─→ Cannot Convert
   └─→ Need New Quote


ALERT STATUS
════════════

🔴 Open/Unresolved
   └─→ Requires Action
   └─→ Still Active
   └─→ Assign to Staff

✓ Resolved
   └─→ Issue Handled
   └─→ No Further Action
   └─→ Archived
```

---

## DAILY CHECKLIST BY ROLE

```
┌────────────────────────────────────────────────────────┐
│           DAILY TASK CHECKLISTS                        │
└────────────────────────────────────────────────────────┘

ADMIN DAILY CHECKLIST
════════════════════

Morning:
  □ Log In to System
  □ Check Dashboard Alerts
  □ Review Overnight Activity
  □ Check Low Stock Products
  □ Read Any Error Messages

Mid-Day:
  □ Monitor System Performance
  □ Review Recent Transactions
  □ Handle User Issues
  □ Approve Any Pending Actions

End of Day:
  □ Review Daily Totals
  □ Check Till Reconciliation
  □ Review Alert Status
  □ Document Any Issues
  □ Plan Tomorrow's Tasks


FINANCE DAILY CHECKLIST
═══════════════════════

Morning:
  □ Log In
  □ Review Overnight Sales
  □ Check Invoices Status
  □ Review Overdue Accounts

Mid-Day:
  □ Monitor Payments Received
  □ Check Quote Conversions
  □ Review Credit Limit Usage
  □ Process Approvals if Needed

End of Day:
  □ Reconcile Daily Sales
  □ Update Account Status
  □ Record Payments
  □ Log Outgoing Invoices
  □ Prepare Tomorrow's Follow Ups


WAREHOUSE DAILY CHECKLIST
═════════════════════════

Morning:
  □ Log In
  □ Check Stock Alerts
  □ Review Overnight Movement
  □ Plan Reception Schedule
  □ Prepare Equipment

Mid-Day:
  □ Receive Any Goods (GRN)
  □ Monitor Stock Levels
  □ Address Any Issues
  □ Review Expiry Warnings
  □ Stock Check of Key Items

End of Day:
  □ Complete All GRNs
  □ Resolve Any Alerts
  □ Audit Movement Records
  □ Prepare Tomorrow's Tasks
  □ Clean Up Work Area


CASHIER DAILY CHECKLIST
══════════════════════

Morning:
  □ Log In
  □ Float Till (Starting Cash)
  □ Test POS Systems
  □ Check Barcode Scanner
  □ Print Daily Report

Throughout Day:
  □ Process Sales Accurately
  □ Accept All Payment Methods
  □ Provide Receipts
  □ Handle Returns Properly
  □ Assist Customers

End of Shift:
  □ Stop Accepting Sales
  □ Count Till Cash
  □ Reconcile with System
  □ Report Variances
  □ Close Shift
  □ Count Tips (if applicable)
  □ Sign Out
```

---

## EMERGENCY CONTACTS

```
┌────────────────────────────────────────────────────────┐
│            EMERGENCY PROCEDURES                        │
└────────────────────────────────────────────────────────┘

COMMON EMERGENCIES & WHO TO CONTACT
═══════════════════════════════════

SCENARIO 1: System Down
  Symptoms: Can't log in, pages won't load
  Contacts: IT Support → Admin
  Action: Manually record transactions until restored
  
SCENARIO 2: Till Discrepancy (Large)
  Symptoms: Missing cash at end of shift
  Contacts: Cashier Supervisor → Manager
  Action: Investigate immediately, don't close
  
SCENARIO 3: Product Quality Issue
  Symptoms: Damaged goods, expiry, contamination
  Contacts: Warehouse Manager → Supplier
  Action: Isolate product, don't sell, document
  
SCENARIO 4: Lost/Stolen Items
  Symptoms: Product missing from shelf, discrepancy
  Contacts: Warehouse Manager → Admin → Police (if large)
  Action: Document loss, review footage if available
  
SCENARIO 5: Payment System Down
  Symptoms: EFTPOS not working
  Contacts: EFTPOS Provider → IT
  Action: Accept cash/credit accounts only
  
SCENARIO 6: User Locked Out
  Symptoms: Forgot password, account disabled
  Contacts: Admin (for reset)
  Action: Temporary access until reset complete
  
SCENARIO 7: Stock Discrepancy at Audit
  Symptoms: Significant difference in physical vs system
  Contacts: Admin → Finance
  Action: Recount, document, investigate
```

---

**END OF WORKFLOW DIAGRAMS**

*Keep this guide near your workstation for quick reference!*
