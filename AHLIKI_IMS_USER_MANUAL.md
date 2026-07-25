# AHLIKI IMS USER MANUAL

## Table of Contents
1. [System Overview](#system-overview)
2. [User Roles & Access Levels](#user-roles--access-levels)
3. [Getting Started](#getting-started)
4. [Admin Workflows](#admin-workflows)
5. [Finance Workflows](#finance-workflows)
6. [Warehouse Workflows](#warehouse-workflows)
7. [Cashier Workflows](#cashier-workflows)
8. [Common Tasks](#common-tasks)
9. [Troubleshooting](#troubleshooting)

---

## System Overview

Ahliki IMS (Inventory Management System) is a comprehensive solution designed to manage products, stock, suppliers, and sales for retail and distribution businesses.

### Key Features
- **Product Management**: Track SKUs, categories, pricing, and stock levels
- **Supplier Management**: Maintain supplier information and purchase orders
- **Stock Receiving**: Document goods received notes (GRN) with batch tracking
- **Point of Sale (POS)**: Fast cashier transactions
- **Invoicing & Quotes**: Generate and manage customer invoices and quotes
- **Stock Alerts**: Real-time low stock and expiry warnings
- **Reports**: Sales and inventory analytics
- **Multi-User Access**: Role-based permissions for different departments

### System Goals
- Maintain accurate real-time inventory
- Streamline purchasing and stock receiving
- Facilitate quick and accurate sales
- Monitor product expiry and stock levels
- Provide financial visibility and reporting

---

## User Roles & Access Levels

### 🔑 Role Hierarchy & Permissions

| Feature | Admin | Finance | Warehouse | Cashier |
|---------|-------|---------|-----------|---------|
| **Dashboard** | ✅ | ✅ | ✅ | ❌ |
| **Products - View** | ✅ | ✅ | ✅ | ✅ |
| **Products - Add/Edit** | ✅ | ✅ | ❌ | ❌ |
| **Categories** | ✅ | ❌ | ❌ | ❌ |
| **Suppliers** | ✅ | ❌ | ❌ | ❌ |
| **Purchase Orders** | ✅ | ❌ | ❌ | ❌ |
| **Goods Received Notes** | ✅ | ❌ | ✅ | ❌ |
| **Stock Movements** | ✅ | ✅ | ✅ | ❌ |
| **Stock Adjustments** | ✅ | ❌ | ✅ | ❌ |
| **POS/Sales** | ✅ | ❌ | ❌ | ✅ |
| **Sales Records** | ✅ | ✅ | ❌ | ❌ |
| **Quotes & Invoices** | ✅ | ✅ | ❌ | ❌ |
| **Alerts** | ✅ | ✅ | ✅ | ❌ |
| **Reports** | ✅ | ✅ | ❌ | ❌ |
| **User Management** | ✅ | ❌ | ❌ | ❌ |

### Role Descriptions

#### 👨‍💼 ADMIN
**Responsibility**: Overall system management and configuration
- System setup and maintenance
- User account management
- Product and supplier catalog management
- Access to all features
- Authority to make system-wide changes

#### 💰 FINANCE
**Responsibility**: Financial oversight and reporting
- Monitoring sales and revenue
- Viewing purchase orders and costs
- Financial reports and analytics
- Product pricing management
- Cannot directly manage stock but can view it

#### 📦 WAREHOUSE
**Responsibility**: Stock management and physical inventory
- Receiving goods from suppliers
- Recording stock movements
- Managing stock levels and alerts
- Stock adjustments and corrections
- Monitoring expiry dates

#### 💳 CASHIER
**Responsibility**: Customer transactions
- Processing customer sales
- Recording cash, credit, and EFTPOS payments
- Issuing receipts
- Limited system access (POS only)

---

## Getting Started

### Logging In

1. Open the Ahliki IMS application in your web browser
2. Enter your **username** and **password**
3. Click **Login**
4. You will be directed to your role-appropriate home screen

### Dashboard Overview

The dashboard displays key metrics relevant to your role:
- **Total Products**: Number of active products in system
- **Low Stock Alerts**: Products below reorder level
- **Recent Activity**: Latest sales and stock receiving
- **Sales Today**: Daily revenue (if applicable)
- **Open Alerts**: System-wide notifications requiring attention

### Navigation Menu

All features are accessible from the left sidebar menu. Menu options change based on your user role.

---

---

# ADMIN WORKFLOWS

## Overview
Admins have full system access and are responsible for:
- User management
- Product and supplier setup
- System configuration
- Authorization and oversight
- Access to all features

---

## Workflow 1: System Setup & Configuration

### Step 1: Create User Accounts

**When**: During initial setup or when new staff joins
**Access**: Users menu

1. Navigate to **Users** → **Add User**
2. Fill in the following fields:
   - **Username**: Unique identifier (e.g., `john_warehouse`)
   - **Password**: Secure password (user can change on first login)
   - **Email**: User's email address
   - **Role**: Select from: Admin, Finance, Warehouse, or Cashier
3. Click **Save**
4. User receives login credentials
5. User should change password on first login

**Notes:**
- Usernames cannot contain spaces
- Passwords should be at least 8 characters
- Role cannot be changed after creation; admin must delete and recreate if needed

---

## Workflow 2: Product Master Data Setup

### Step 2A: Create Product Categories

**When**: Before adding products
**Access**: Categories menu

1. Navigate to **Categories** → **Add Category**
2. Enter **Category Name** (e.g., "Electronics", "Food & Beverages")
3. Add optional **Description**
4. Click **Save**

**Tip**: Create all main categories first to organize products efficiently

---

### Step 2B: Create Suppliers

**When**: Before adding products
**Access**: Suppliers menu

1. Navigate to **Suppliers** → **Add Supplier**
2. Fill in supplier details:
   - **Company Name**: Official supplier name
   - **Contact Name**: Primary contact person
   - **Phone**: Contact number
   - **Email**: Email address
   - **Address**: Physical address
3. Click **Save**

**Tip**: Verify supplier contact information for smooth order processing

---

### Step 2C: Add Products

**When**: Initial setup or when stocking new products
**Access**: Products → **Add Product**

1. Navigate to **Products** → **Add Product**
2. Fill in all product details:

| Field | Description | Example |
|-------|-------------|---------|
| **SKU** | Unique product code | PRD-001-ELC |
| **Product Name** | Full product name | 32-inch LED TV |
| **Category** | Select from categories | Electronics |
| **Supplier** | Select supplier | TechSupply Inc |
| **Unit Price** | Selling price | 15,000 SAT |
| **Cost Price** | Purchase cost | 10,000 SAT |
| **Reorder Level** | Alert threshold | 5 units |
| **Unit** | Measurement unit | each, kg, litre, carton |
| **Barcode** | Optional barcode | 123456789012 |
| **Description** | Additional details | 4K, Smart TV |

3. Click **Save**

**Important Notes:**
- SKU must be unique (system won't allow duplicates)
- Cost Price is used for financial calculations
- Reorder Level triggers low stock alerts
- Products start with Active status enabled

---

## Workflow 3: Oversight & Monitoring

### Step 3A: Review System Alerts

**When**: Daily
**Access**: Dashboard → Alerts section

1. Log in to Dashboard
2. View **Open Alerts** section (top right)
3. Check alert types:
   - **Low Stock**: Product needs reordering
   - **Expiry Warning**: Products expiring within 30 days
   - **GRN Discrepancy**: Received quantity doesn't match order
4. Click on alert for details
5. Assign to appropriate team member (Warehouse for stock, Finance for ordering)

---

### Step 3B: View and Audit User Activity

**When**: As needed for audits or troubleshooting
**Access**: Reports → Stock Movements

1. Navigate to **Reports**
2. View **Stock Movements** section
3. Filter by:
   - Date range
   - User (performed by)
   - Movement type
4. Export report if needed for records

---

## Workflow 4: Financial Overview

### Step 4: View Financial Dashboard

**When**: Weekly or monthly
**Access**: Dashboard

Key metrics to review:
- **Stock Value**: Total value of inventory at cost
- **Sales Today**: Daily revenue
- **Low Stock Products**: Products needing reorder
- **Sales Chart**: 7-day sales trend

**Actions**:
- Monitor stock value for working capital
- Alert Finance team if stock value exceeds threshold
- Ensure adequate stock for high-demand products

---

## Workflow 5: System Maintenance

### Step 5A: Manage Product Updates

**When**: Products change pricing, reorder levels, or details
**Access**: Products → Product Details → Edit

1. Navigate to **Products**
2. Search for product by name or SKU
3. Click on product to view details
4. Click **Edit**
5. Update necessary fields:
   - Pricing (Cost or Unit)
   - Reorder level
   - Supplier
   - Status (deactivate if discontinued)
6. Click **Save**

**Warning**: Changing pricing only affects new sales; past transactions unchanged

---

### Step 5B: Deactivate Discontinued Products

**When**: Product is no longer sold
**Access**: Products → Edit

1. Navigate to **Products**
2. Find the product
3. Click **Edit**
4. Uncheck **Active** checkbox
5. Click **Save**

**Result**: Product hidden from POS and product lists, but remains in records for historical accuracy

---

---

# FINANCE WORKFLOWS

## Overview
Finance team monitors financial health, manages costs, and generates reports:
- Revenue tracking
- Cost analysis
- Customer credit management
- Financial reporting
- Product pricing oversight

---

## Workflow 1: Daily Sales Monitoring

### Step 1: Review Daily Sales

**When**: End of business day
**Access**: Dashboard / Sales

1. Log in to Dashboard
2. Review **Sales Today** section showing:
   - Total daily revenue
   - Number of transactions
   - Sales by payment method (Cash/Credit/EFTPOS)

3. For detailed breakdown:
   - Navigate to **Sales** menu
   - Click on sales date or today's sales
   - View individual transactions

4. Verify totals match till (POS) records if available

---

## Workflow 2: Manage Customer Credit Accounts

### Step 2A: Create Invoices for Credit Customers

**When**: Customer makes credit purchase
**Access**: Invoices → New Invoice

1. Navigate to **Invoices** → **Create Invoice**
2. Fill in invoice details:
   - **Customer Name**: Business or individual name
   - **Account Number**: BC account number (if applicable)
   - **Invoice Date**: Auto-populated (today)
3. Add line items:
   - Click **Add Item**
   - Select **Product** from dropdown
   - Enter **Quantity**
   - Unit Price auto-populates
4. System calculates **Total Amount**
5. Add optional **Notes** (payment terms, special conditions)
6. Click **Save Invoice**

**Result**: Invoice generated with unique invoice number

---

### Step 2B: Track Invoice Payments

**When**: Following up on payments
**Access**: Invoices

1. Navigate to **Invoices**
2. Find invoice by:
   - Customer name
   - Invoice number
   - Date range
3. View invoice status:
   - **Unpaid**: Outstanding payment
   - **Paid**: Payment received
   - **Overdue**: Payment past due date
4. To mark as paid:
   - Click on invoice
   - Click **Mark as Paid**
   - Enter payment date and method
   - Click **Confirm**

**Tip**: Track overdue invoices to improve cash flow

---

## Workflow 3: Generate Quotes

### Step 3: Create Customer Quotes

**When**: Customer requests pricing before purchase
**Access**: Quotes → New Quote

1. Navigate to **Quotes** → **Create Quote**
2. Enter quote details:
   - **Customer Name**
   - **Quote Date**: Auto-populated
3. Add line items:
   - Click **Add Item**
   - Select **Product**
   - Enter **Quantity**
   - Verify pricing
4. System shows **Total Price** with potential discount
5. Add optional **Notes** (quote valid until date, conditions)
6. Click **Save Quote**

**Result**: Unique quote generated with number

---

### Step 3B: Convert Quote to Invoice

**When**: Customer accepts quote and purchases
**Access**: Quotes

1. Navigate to **Quotes**
2. Find and click the quote to convert
3. Click **Convert to Invoice**
4. Review details (can be edited)
5. Click **Confirm Conversion**

**Result**: 
- Quote marked as converted
- New invoice created with same items
- Ready for delivery/payment

---

## Workflow 4: Financial Reporting

### Step 4A: Generate Sales Reports

**When**: Weekly, monthly, or on-demand
**Access**: Reports → Export Sales

1. Navigate to **Reports**
2. Select **Sales Report**
3. Set filters:
   - **Date Range**: From and To dates
   - **Cashier**: (Optional) specific cashier
   - **Payment Method**: Filter by Cash/Credit/EFTPOS
4. Review report showing:
   - Total sales
   - Number of transactions
   - Average transaction value
   - Sales by payment method
5. To export:
   - Click **Export as CSV**
   - Save file to computer
   - Open in Excel for analysis

**Common Uses**:
- Daily revenue reconciliation
- Weekly trend analysis
- Monthly financial statements

---

### Step 4B: Generate Stock Valuation Report

**When**: Month-end, audit, or financial review
**Access**: Reports → Export Stock

1. Navigate to **Reports**
2. Select **Stock Report**
3. Report shows:
   - Current stock quantity per product
   - Unit cost price
   - Total stock value (quantity × cost)
   - Low stock alerts
4. To export:
   - Click **Export as CSV**
   - Use for financial statements
   - Verify against physical count

**Important**: Stock value = key asset on balance sheet

---

## Workflow 5: Cost Price Management

### Step 5: Review and Update Product Costs

**When**: Supplier prices change
**Access**: Products → Edit

1. Navigate to **Products**
2. Search for product
3. Click product to view details
4. Click **Edit**
5. Update **Cost Price** field with new supplier cost
6. Click **Save**

**Note**: 
- Only Finance and Admin can edit cost prices
- Changes affect future profitability calculations
- Does not affect past transactions

---

## Workflow 6: Monitor Profitability

### Step 6: Analyze Product Margins

**When**: Monthly
**Access**: Dashboard / Reports

Review profitability:

For each product category:
- **Margin** = Unit Price - Cost Price
- **Margin %** = (Margin / Unit Price) × 100

Example:
- Product: Item X
- Cost Price: 100 SAT
- Unit Price: 250 SAT
- Margin: 150 SAT
- Margin %: 60%

**Actions**:
- Identify low-margin products
- Review pricing strategy
- Alert admin if margins concerning
- Consider supplier negotiation for better rates

---

---

# WAREHOUSE WORKFLOWS

## Overview
Warehouse team manages physical inventory:
- Receiving goods from suppliers
- Recording stock movements
- Monitoring stock levels
- Managing expiry dates
- Stock accuracy and audits

---

## Workflow 1: Receiving Goods from Suppliers

### Step 1A: Prepare for Stock Receiving

**When**: Goods arrive from supplier
**Access**: GRN (Goods Received Notes)

Before goods arrive:

1. Verify **Purchase Order** exists:
   - Navigate to **Dashboard** 
   - Check **Open POs** section
   - Note PO number and expected items

2. Prepare receiving area:
   - Clear space for inspection
   - Gather receiving documents
   - Set up scale if needed

---

### Step 1B: Record Goods Received Note (GRN)

**When**: Goods physically received
**Access**: GRN → Create GRN

1. Navigate to **GRN** → **Add GRN**
2. Fill in GRN details:
   - **GRN Number**: System auto-generates unique number
   - **Supplier**: Select supplier
   - **Purchase Order** (Optional): Link to PO if applicable
3. For each item received:
   - Click **Add Item**
   - Select **Product** from list
   - Enter **Quantity Received** (actual count)
   - Enter **Batch Number** (if applicable)
   - Enter **Expiry Date** (if applicable)
   - **Unit Cost**: Should auto-populate from PO
4. Add optional **Notes** (condition, damage, etc.)
5. Click **Save GRN**

**Result**: 
- GRN number generated and recorded
- Stock immediately increased
- Stock movements tracked
- Alerts created if low stock or expiry warning

---

### Step 1C: Handle Receiving Discrepancies

**If quantity received doesn't match PO**:

1. After saving GRN, system shows **Discrepancy Alert**
2. Click on alert details
3. Note shows:
   - **Ordered**: Qty from PO
   - **Received**: Actual qty
   - **Difference**: Variance amount
4. Options:
   - **Contact Supplier**: For short shipment
   - **Amend PO**: If partial expected
   - **Document Issue**: Note in system for follow-up
5. Forward discrepancy alert to Admin/Finance

**Common Scenarios**:
- Partial shipment (received less than ordered)
- Over-delivery (received more than ordered)
- Damaged items (reduce received qty)
- Wrong items (contact supplier immediately)

---

## Workflow 2: Managing Stock Levels

### Step 2A: View Current Stock

**When**: Daily or on-demand
**Access**: Products → Product Details

1. Navigate to **Products**
2. Browse or search for product
3. Click product name to view details
4. View **Current Stock** displayed at top
5. Check against **Reorder Level**

**Indicators**:
- ✅ Green = Adequate stock
- 🟠 Orange = Low stock (below reorder level)
- 🔴 Red = Critical (needs urgent reorder)

---

### Step 2B: Monitor Stock Movements

**When**: End of shift or on-demand
**Access**: Stock → Movements

1. Navigate to **Stock** → **View Movements**
2. Review recent stock changes showing:
   - Product name
   - Movement type (In/Out/Adjustment)
   - Quantity changed
   - Date and time
   - Performed by (username)
   - Reference (GRN number or Sale number)
3. Verify movements match physical actions

**Tip**: Use for auditing and reconciliation

---

## Workflow 3: Stock Adjustments

### Step 3: Record Stock Adjustments

**When**: 
- Physical count reveals discrepancies
- Damage/loss discovered
- Inventory audit
**Access**: Stock → Adjust

1. Navigate to **Stock** → **Adjust Stock**
2. For each adjustment needed:
   - **Select Product**: From dropdown
   - **Current Stock**: System shows actual
   - **Adjustment Quantity**: 
     - Positive number = Add to stock
     - Negative number = Reduce stock
   - **Reason**: Select from:
     - Loss/Damage
     - Physical Count Variance
     - Return from Sale
     - Theft/Spillage
     - Other
   - **Notes**: Detailed explanation
3. Click **Save Adjustment**

**Example**:
- Counted 8 units of Product X
- System shows 10 units
- Discrepancy: 2 units
- Create adjustment: -2 units
- Reason: Physical count variance

---

## Workflow 4: Monitor Alerts

### Step 4A: Review Stock Alerts

**When**: Multiple times daily
**Access**: Alerts menu

1. Navigate to **Alerts**
2. View all open alerts showing:
   - **Alert Type**: Low Stock, Expiry Warning, Discrepancy
   - **Product**: Item affected
   - **Message**: Details
   - **Created**: When alert triggered
3. Click alert to view full details

---

### Step 4B: Resolve Low Stock Alerts

**When**: Product stock falls below reorder level

1. Click **Low Stock** alert
2. View details:
   - Current stock level
   - Reorder level
   - Shortage amount
3. Take action:
   - **Option A**: Escalate to Admin to create PO
   - **Option B**: Check incoming GRNs for delivery
   - **Option C**: Note in alert for follow-up
4. Click **Resolve Alert** when issue addressed

---

### Step 4C: Manage Expiry Warnings

**When**: Products approaching expiry date

1. Click **Expiry Warning** alert
2. View details:
   - **Product**: Item expiring
   - **Batch Number**: Specific batch
   - **Expiry Date**: When expires
   - **Days Remaining**: Time until expiry
3. Actions:
   - **Sell First**: Mark for priority sales
   - **Dispose**: If unusable, create adjustment
   - **Return**: Contact supplier if applicable
4. Click **Resolve Alert** after handling

---

## Workflow 5: Physical Inventory Audit

### Step 5: Conduct Inventory Count

**When**: Monthly or per management request
**Access**: Stock → Movements

**Process**:

1. **Preparation** (Before count):
   - Print current stock report from system
   - Prepare counting sheets
   - Divide warehouse into zones

2. **Physical Count** (Execution):
   - Count all items in each zone
   - Record actual quantity on sheet
   - Compare to system quantity
   - Note discrepancies

3. **Recording** (After count):
   - For each variance found:
     - Navigate to **Stock** → **Adjust Stock**
     - Select product
     - Enter adjustment (actual minus system qty)
     - Reason: "Physical Count Variance"
     - Save

4. **Verification**:
   - Recount high-value items
   - Investigate large variances
   - Document findings

---

## Workflow 6: Supplier Communication

### Step 6: Follow Up on Stock Issues

**When**: Damaged goods, shortages, or quality issues

1. Document issue:
   - Product name and SKU
   - Quantity affected
   - Nature of issue
   - Date discovered
   - Photo if applicable

2. Contact supplier:
   - Reference GRN number
   - Reference PO number
   - Explain issue clearly
   - Request resolution (credit, replacement, etc.)

3. Record action in system:
   - Add note to GRN
   - Create alert if inventory affected
   - Forward to Admin/Finance for follow-up

---

---

# CASHIER WORKFLOWS

## Overview
Cashiers process customer transactions efficiently:
- Fast and accurate sales
- Multiple payment methods
- Customer service
- Receipt generation
- POS (Point of Sale) operations

---

## Workflow 1: Daily POS Operations

### Step 1A: Start of Day

**When**: Beginning of shift
**Access**: POS

1. Log in to system with cashier credentials
2. Navigate to **POS** (Point of Sale)
3. POS screen opens with:
   - Current date/time
   - Till status
   - Ready for transactions

---

### Step 1B: Process Cash Sale

**When**: Customer purchases with cash
**Access**: POS

1. **Ring in items**:
   - Click **Scan/Add Items** button
   - Enter product SKU or barcode
   - System finds product and displays name, price
   - Enter **Quantity** needed
   - Click **Add to Sale**
   - Repeat for each item

2. **Review Sale Cart**:
   - See all items added
   - **Quantity**, **Unit Price**, **Line Total** shown
   - **Subtotal** displayed
   - Remove items if needed by clicking **Remove**

3. **Complete Payment**:
   - Click **Checkout**
   - **Payment Method**: Select **Cash**
   - **Amount Tendered**: Enter cash given by customer
   - System calculates **Change**
   - Review payment summary

4. **Finalize**:
   - Click **Complete Sale**
   - Receipt prints automatically
   - Sale recorded with unique number
   - Till updated
   - New sale screen ready

**Example Transaction**:
```
Item 1: Bread × 2 @ 50 = 100 SAT
Item 2: Milk × 1 @ 80 = 80 SAT
Item 3: Butter × 1 @ 120 = 120 SAT
                  Subtotal: 300 SAT
              Amount Paid: 500 SAT
                   Change: 200 SAT
```

---

### Step 1C: Process Credit Sale

**When**: Customer has credit account
**Access**: POS

1. Add items to sale (same as cash)
2. Click **Checkout**
3. **Payment Method**: Select **Credit Account**
4. Enter **Account Number** (BC account):
   - System validates account
   - Shows account holder name
5. Enter **Customer Name** if different
6. Review and confirm payment method
7. Click **Complete Sale**

**Result**: 
- Sale recorded as credit
- Invoice generated for customer
- Amount added to customer account
- Finance team notified for follow-up

---

### Step 1D: Process EFTPOS Payment

**When**: Customer uses card (Debit/Credit Card)
**Access**: POS

1. Add items to sale
2. Click **Checkout**
3. **Payment Method**: Select **EFTPOS**
4. **Card Amount**: Confirm total
5. Customer inserts or taps card at EFTPOS device
6. System displays **Processing**...
7. Once approved:
   - Receipt prints
   - Sale completed
   - Amount shown in till

**Tip**: Don't process sale until EFTPOS approval confirmed

---

## Workflow 2: Handle Special Situations

### Step 2A: Void/Cancel Sale

**When**: Customer cancels before payment or payment fails
**Access**: POS

**Before Payment**:
1. Click **Clear Cart** - removes all items
2. Start new sale

**After Payment Failed**:
1. Contact manager/supervisor
2. Manager can void transaction from system
3. Clear cart and process again

---

### Step 2B: Apply Discount

**When**: Manager approval for discount
**Access**: POS (if enabled)

**Process**:
1. Add items to sale as normal
2. Before checkout, click **Apply Discount**
3. Discount options:
   - **Percentage**: e.g., 10% off
   - **Fixed Amount**: e.g., 50 SAT off
4. Enter discount amount
5. Enter **Discount Reason**: 
   - Promotional
   - Damaged Goods
   - Manager Approval
6. Discount applied to subtotal
7. Complete payment

**Important**: Some discounts require manager password

---

### Step 2C: Handle Return/Exchange

**When**: Customer returns items

**Process**:
1. Customer presents item and receipt
2. Verify item is in resalable condition
3. Verify purchase within return window (typically 7-30 days)
4. Process return:
   - Click **Process Return**
   - Enter **Sale Number** from receipt
   - Select **Item** to return
   - Enter **Return Quantity**
   - Select **Reason**: Defective, Changed Mind, Damage
   - Click **Process**
5. System creates credit:
   - Refund to original payment method
   - Or store credit
6. Stock increased by return quantity

---

## Workflow 3: Till Management

### Step 3A: Till Operations

**During Shift**:
- Keep till secure
- Count cash periodically
- Reconcile to system
- Report discrepancies to manager

**End of Shift**:
1. Click **Till Reconciliation**
2. System shows expected till total (sum of cash sales)
3. Count actual cash in till
4. Enter **Actual Count**
5. System calculates variance:
   - Expected: 50,000 SAT
   - Actual: 49,950 SAT
   - Variance: -50 SAT (Short)
6. Investigate variances
7. Click **Confirm**
8. Report to manager with explanation

---

### Step 3B: Shift Report

**End of Shift**:
1. Navigate to **Sales** → **Today's Report**
2. View shift totals:
   - Cash sales
   - Credit sales
   - EFTPOS sales
   - Total transactions
   - Total revenue
   - Average transaction
3. Print report for records
4. Give to supervisor/manager

---

## Workflow 4: Daily Closing

### Step 4: Close POS

**End of Business Day**:

1. Ensure no pending transactions
2. Reconcile till with system
3. Back up sales data (automatic)
4. Click **Close POS**
5. System shows:
   - Total sales today
   - Total transactions
   - Payment breakdown
6. Manager reviews and approves
7. Till closed - no more transactions allowed

**Next Day**: Log in again to open new till

---

## Workflow 5: Handle Common Issues

### Issue 1: Product Not Found

**If SKU/Barcode doesn't scan**:
1. Check barcode for damage or dirt - clean if needed
2. Re-scan
3. If still not found:
   - Click **Manual Search**
   - Search by product name
   - Select correct product
4. If product not in system:
   - Contact manager/warehouse
   - May not be set up in inventory yet

---

### Issue 2: Insufficient Stock

**If product quantity unavailable**:
1. POS shows "Insufficient Stock"
2. Enter available quantity instead
3. Inform customer of lower quantity
4. Complete sale with available amount
5. Alert manager/warehouse staff

---

### Issue 3: System Slow/Unresponsive

**If POS becomes slow**:
1. Wait 10-15 seconds (system may be processing)
2. If still slow:
   - Note sale items
   - Contact IT support
   - Manually record transaction
   - Process when system back online

---

## Workflow 6: Customer Service

### Step 6: Excellent Cashier Practices

**Before Sale**:
- Greet customer warmly
- Confirm they're ready to checkout
- Ask if they need bags

**During Sale**:
- Ring items carefully
- Ask if customer has discount card
- Verify correct product selected
- Confirm total with customer

**During Payment**:
- Thank customer for payment
- Process payment method correctly
- Provide receipt
- For cash: count change back carefully

**After Sale**:
- "Thank you, have a great day!"
- Bag items neatly
- Ensure customer has receipt
- "Please come again!"

---

---

# COMMON TASKS

## Task 1: Searching for Products

**Across the system**, search for products using multiple methods:

### Method 1: By SKU (Fastest)
- **If you know SKU**: PRD-001
- Go to **Products**
- Enter SKU in search box
- Product appears immediately

### Method 2: By Name
- Go to **Products**
- Enter product name (or partial name)
- System finds all matches
- Click to select

### Method 3: By Category
- Go to **Products**
- Use **Category Filter** dropdown
- Select category
- All products in that category shown

### Method 4: By Barcode
- (POS Only) Scan barcode with scanner
- Product automatically added

---

## Task 2: Viewing Historical Data

### Stock Movement History
1. Navigate to **Stock** → **Movements**
2. View all stock changes with:
   - Date/Time
   - Product
   - Quantity changed
   - Person who made change
   - Reference (GRN/Sale)
3. Filter by date range or product
4. Export to CSV if needed

### Sales History
1. Navigate to **Sales**
2. Browse sales by date
3. Click sale to see:
   - Items sold
   - Quantities
   - Prices
   - Payment method
   - Cashier name

### GRN History
1. Navigate to **GRN**
2. View all receiving records
3. Click GRN to see:
   - Items received
   - Quantities
   - Batch/Expiry info
   - Supplier
   - Receiving staff

---

## Task 3: Changing Your Password

**For any user role**:

1. Click your **Profile** (top right menu)
2. Click **Change Password**
3. Enter **Current Password**
4. Enter **New Password**:
   - At least 8 characters
   - Mix of letters and numbers recommended
5. Confirm **New Password** (type again)
6. Click **Save**
7. You're logged out - log in with new password

**Security Tips**:
- Don't share passwords
- Change password monthly
- Use unique passwords
- Never write password down

---

## Task 4: Viewing Your Profile

1. Click your **Profile** (top right)
2. View your details:
   - Username
   - Email
   - Role
   - Department
3. Update email if needed:
   - Edit email field
   - Click **Save**

---

## Task 5: Generating Reports

### Sales Report
1. Navigate to **Reports**
2. Select **Sales Report**
3. Set date range:
   - **From**: Start date
   - **To**: End date
4. Optional filters:
   - Cashier name
   - Payment method
5. Click **Generate**
6. View or export results

### Stock Report
1. Navigate to **Reports**
2. Select **Stock Report**
3. Shows current quantities and values
4. Export for accounting/audit

---

## Task 6: Understanding Alerts

| Alert Type | What It Means | Action |
|-----------|--------------|--------|
| **Low Stock** | Item below reorder level | Order from supplier; marked urgent |
| **Expiry Warning** | Product expiring within 30 days | Promote sales or prepare for disposal |
| **GRN Discrepancy** | Received qty ≠ ordered qty | Contact supplier; follow up with order |

**View Alerts**:
1. Go to **Alerts**
2. See all open issues
3. Click to view details
4. Mark **Resolve** when handled

---

---

# TROUBLESHOOTING

## Common Issues & Solutions

### Issue: "Insufficient Stock" when receiving GRN

**Problem**: Can't complete GRN for an item
**Cause**: Item not in system
**Solution**:
1. Check if product exists in Products
2. If not, create product first (Admin only)
3. Then try GRN again

---

### Issue: Can't see certain menu options

**Problem**: Menu option missing or grayed out
**Cause**: Your user role doesn't have permission
**Solution**:
1. Check your role (Profile menu)
2. Request permission from Admin if needed
3. Admin may need to create new user with correct role

**Permission Levels**:
- **Admin**: Full access
- **Finance**: Reporting only
- **Warehouse**: Stock management only
- **Cashier**: POS only

---

### Issue: Product in system but barcode won't scan

**Problem**: Barcode not recognized at POS
**Cause**: Barcode in system doesn't match physical barcode
**Solution**:
1. Manually search product by name
2. Contact warehouse to verify barcode
3. Admin updates barcode in system if needed

---

### Issue: Sales total doesn't match till

**Problem**: System says $500 sold but till has $450
**Cause**: Multiple possibilities - discounts, voids, returns, shortages
**Solution**:
1. Review till reconciliation report
2. Check for:
   - Applied discounts
   - Voided sales
   - Returns processed
   - Payment method mismatches
3. Contact manager to investigate variance

---

### Issue: Forgot password

**Problem**: Can't log in
**Solution**:
1. **Try**: Check CAPS LOCK is off
2. **Try**: Verify username is correct
3. **Contact**: Admin or IT support for password reset
4. Admin can reset from Users menu

---

### Issue: System running slowly

**Problem**: POS/Pages load slowly
**Cause**: Network issue, busy server, or browser cache
**Solution**:
1. Refresh page (Cmd+R or Ctrl+R)
2. Clear browser cache
3. Check internet connection
4. Try different browser
5. Contact IT if persists

---

### Issue: Barcode scanner not working

**Problem**: Barcode scan not registering at POS
**Cause**: Scanner disconnected, misconfigured, or batteries dead
**Solution**:
1. Check scanner batteries
2. Reconnect scanner
3. Test with known barcode
4. If still not working:
   - Use manual search
   - Contact IT support

---

### Issue: Can't create Purchase Order

**Problem**: "You don't have permission"
**Cause**: Not admin, or no supplier selected
**Solution**:
1. Ensure supplier exists first (Admin creates)
2. Admin only can create POs
3. Contact admin to create PO

---

### Issue: Discount or return won't process

**Problem**: "Not allowed" message
**Cause**: Requires manager approval
**Solution**:
1. Call manager to counter/POS
2. Manager enters override code
3. Discount/return completed

---

## Getting Help

### Contacts by Issue

| Issue Type | Contact | Method |
|-----------|---------|--------|
| User/Permission | Admin | In-person or phone |
| Technical | IT Support | Email or call |
| Inventory | Warehouse Manager | In-person or phone |
| Financial | Finance Manager | In-person or email |
| Sales | Cashier Supervisor | In-person |

### Before Contacting Support

1. Try refreshing the page
2. Log out and log back in
3. Document the error message
4. Note what you were doing
5. Have a screenshot if possible

---

---

## QUICK REFERENCE GUIDE

### Admin Quick Links
- 🔧 **User Management**: Users → Add/Edit
- 📦 **Products**: Products → Add/Edit
- 🏭 **Suppliers**: Suppliers → Add
- 📂 **Categories**: Categories → Add
- 🔔 **Alerts**: Alerts → Review

### Finance Quick Links
- 📊 **Dashboard**: Dashboard
- 💵 **Sales**: Sales → View
- 💳 **Invoices**: Invoices → Create/Track
- 📋 **Quotes**: Quotes → Create/Convert
- 📈 **Reports**: Reports → Generate

### Warehouse Quick Links
- 📥 **GRN**: GRN → Add
- 📦 **Stock**: Stock → Movements/Adjust
- 🔔 **Alerts**: Alerts → Review
- 🔍 **Search**: Products → Search

### Cashier Quick Links
- 💰 **POS**: POS → Process Sale
- 🧾 **Receipt**: POS → Print
- 📝 **Transactions**: Sales → View

---

### Keyboard Shortcuts (POS)

| Shortcut | Action |
|----------|--------|
| **Enter/Return** | Add item to cart |
| **Backspace** | Remove last item |
| **Tab** | Move to next field |
| **Cmd/Ctrl + P** | Print receipt |
| **Cmd/Ctrl + S** | Save/Complete sale |
| **Escape** | Clear/Cancel |

---

### Standard Measurements

| Unit | Meaning | Common Products |
|------|---------|-----------------|
| **each** | Individual unit | Books, boxes, items |
| **kg** | Kilogram | Rice, sugar, flour |
| **litre** | Liter | Oil, milk, juice |
| **carton** | Box/carton | Eggs (12), milk (6), etc.) |
| **dozen** | 12 units | Eggs, items sold by 12 |
| **gram** | Gram | Spices, small items |

---

### Currency Reference
- **SAT** = System currency (appears as "SAT" in displays)
- All amounts shown with 2 decimal places
- Example: 1,500.50 SAT

---

## Support & Feedback

**System Issues?**
- Document the problem
- Note error messages
- Contact IT Support with details

**Suggestions for Improvement?**
- Contact Admin
- Describe suggested feature
- Explain how it would help

**Training Needed?**
- Each role receives role-specific training
- Contact your manager for refresher training
- Admin can provide additional user training

---

## Document Version & Updates

**Version**: 1.0
**Date**: May 2026
**System**: Ahliki IMS v1.0
**Last Updated**: 2026-05-13

---

**END OF USER MANUAL**

---

*This manual should be printed and available in the office. Keep it updated as features change. For the most recent version, contact the Admin team.*
