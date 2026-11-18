"""LS Central connection — template.

Copy this file to ls_central_config.py in the same folder and fill in the values.
ls_central_config.py is git-ignored and kept out of Docker images, so the keys never
get committed. On Azure, set the same names as Application settings instead; for the
office Docker install, put them in .env.

Where to find each value (Azure portal → Microsoft Entra ID → App registrations → your app):
"""

# Overview page → "Directory (tenant) ID".
LS_CENTRAL_TENANT_ID = ''

# Overview page → "Application (client) ID".
LS_CENTRAL_CLIENT_ID = ''

# Certificates & secrets → New client secret → copy the "Value" (not the Secret ID).
# It is shown only once. Note its expiry date — the sync stops when it expires.
LS_CENTRAL_CLIENT_SECRET = ''

# Business Central environment name, as shown in the LS Central URL or the admin center,
# e.g. 'Production' or 'Sandbox'.
LS_CENTRAL_ENVIRONMENT = ''

# Company to read invoices from — its name exactly as in LS Central (e.g. 'Ah Liki Wholesale Ltd'),
# or its id (a GUID). Leave blank if the environment has only one company.
LS_CENTRAL_COMPANY = ''

# ── Optional — the defaults suit LS Central in the cloud ──────────────────────

# Which invoice statuses to import: 'Open' (posted, unpaid) and 'Paid'. Add 'Draft' to also
# import invoices that are not posted yet.
# LS_CENTRAL_INVOICE_STATUSES = ['Open', 'Paid']

# How many days back to look for invoices on each sync.
# LS_CENTRAL_SYNC_DAYS = 7

# How often the website checks LS Central for new invoices, in minutes. 0 turns it off
# (the "Sync now" button and `manage.py sync_ls_central` still work).
# LS_CENTRAL_SYNC_MINUTES = 10

# Only change for LS Central on-premises or a custom API page.
# LS_CENTRAL_API_URL = 'https://api.businesscentral.dynamics.com/v2.0'
# LS_CENTRAL_API_PATH = 'api/v2.0'
