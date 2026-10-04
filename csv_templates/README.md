# CSV import templates

These are the same files the admin serves from **Download CSV template**, kept here for reference.

Where to import (superuser / staff login required):

| Data | Admin page | Import URL |
| --- | --- | --- |
| Categories | Inventory → Categories | `/admin/inventory/category/import-csv/` |
| Suppliers | Inventory → Suppliers | `/admin/inventory/supplier/import-csv/` |
| Products | Inventory → Products | `/admin/inventory/product/import-csv/` |

On each of those list pages there are two buttons at the top right: **Import CSV** and
**Download CSV template**.

## Rules

* The file must be UTF-8 CSV. In Excel: *Save As → CSV UTF-8 (Comma delimited)*.
* The header row must keep the exact column names below. Extra columns are ignored.
* Rows are **upserted**: matched on the unique key, created if new, updated if it already exists.
  * Category / Supplier key = `name`
  * Product key = `sku`
* On an update, blank optional cells leave the existing value alone.
* Blank rows are skipped. A bad row is reported by line number and the rest still import.

## Columns

**categories_template.csv**

| Column | Required | Notes |
| --- | --- | --- |
| name | yes | Unique key |
| description | no | Free text |

**suppliers_template.csv**

| Column | Required | Notes |
| --- | --- | --- |
| name | yes | Unique key |
| contact_name | no | |
| phone | no | |
| email | no | Must be a valid email if given |
| address | no | |

**products_template.csv**

| Column | Required | Notes |
| --- | --- | --- |
| sku | yes | Unique key |
| name | yes | |
| category | no | Category name — created automatically if missing |
| supplier | no | Supplier name — created automatically if missing |
| unit_price | no | e.g. `12.50`; defaults to 0 |
| cost_price | no | e.g. `8.00`; defaults to 0 |
| reorder_level | no | Whole number; defaults to 10 |
| unit | no | e.g. `each`, `kg`, `carton`; defaults to `each` |
| barcode | no | |
| description | no | |
| is_active | no | `yes`/`no`, `true`/`false`, `1`/`0`; defaults to yes |

Import order does not matter — importing products alone will create any missing
categories and suppliers by name. Import categories and suppliers first if you want
their descriptions and contact details filled in.
