"""Reads sales invoices from LS Central through the Business Central API.

Signs in as the Microsoft Entra app registration (client credentials) — no user account
needed. The app must also be added in LS Central on the "Microsoft Entra Applications" page
with read permission (e.g. the D365 READ permission set) and granted consent.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

TOKEN_URL = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'
SCOPE = 'https://api.businesscentral.dynamics.com/.default'
TIMEOUT = 30
REQUIRED = ('LS_CENTRAL_TENANT_ID', 'LS_CENTRAL_CLIENT_ID', 'LS_CENTRAL_CLIENT_SECRET', 'LS_CENTRAL_ENVIRONMENT')


class LsCentralError(Exception):
    """Something went wrong talking to LS Central; the message is safe to show to staff."""


class NotConfigured(LsCentralError):
    pass


def missing_settings():
    return [name for name in REQUIRED if not getattr(settings, name, '')]


def is_configured():
    return not missing_settings()


_token_cache = {}   # client id -> (token, expires at)


class LsCentralClient:
    def __init__(self, tenant, client_id, client_secret, environment, company='',
                 api_url='https://api.businesscentral.dynamics.com/v2.0', api_path='api/v2.0'):
        self.tenant = tenant
        self.client_id = client_id
        self.client_secret = client_secret
        self.environment = environment
        self.company = company
        self.root = f'{api_url.rstrip("/")}/{tenant}/{environment}'
        self.base = f'{self.root}/{api_path.strip("/")}'
        self._company_id = None
        self._company_name = None

    @classmethod
    def from_settings(cls):
        missing = missing_settings()
        if missing:
            raise NotConfigured('LS Central is not set up yet — missing ' + ', '.join(missing) +
                                ' in ahliki_ims/ls_central_config.py.')
        return cls(settings.LS_CENTRAL_TENANT_ID, settings.LS_CENTRAL_CLIENT_ID,
                   settings.LS_CENTRAL_CLIENT_SECRET, settings.LS_CENTRAL_ENVIRONMENT,
                   settings.LS_CENTRAL_COMPANY, settings.LS_CENTRAL_API_URL, settings.LS_CENTRAL_API_PATH)

    # ── HTTP ────────────────────────────────────────────────────────────────

    def _token(self):
        cached = _token_cache.get(self.client_id)
        if cached and cached[1] > time.time() + 60:
            return cached[0]
        body = urllib.parse.urlencode({
            'grant_type': 'client_credentials', 'client_id': self.client_id,
            'client_secret': self.client_secret, 'scope': SCOPE,
        }).encode()
        data = self._open(urllib.request.Request(TOKEN_URL.format(tenant=self.tenant), data=body), signing_in=True)
        token = data.get('access_token')
        if not token:
            raise LsCentralError('Microsoft sign-in did not return a token.')
        _token_cache[self.client_id] = (token, time.time() + int(data.get('expires_in', 3600)))
        return token

    def _open(self, request, signing_in=False):
        request.add_header('Accept', 'application/json')
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode('utf-8') or '{}')
        except urllib.error.HTTPError as exc:
            detail = _error_text(exc)
            if signing_in:
                raise LsCentralError(f'Microsoft sign-in failed ({exc.code}): {detail} '
                                     'Check the tenant ID, client ID and client secret.') from None
            if exc.code == 401:
                raise LsCentralError('LS Central refused the app (401). Add it on the "Microsoft Entra '
                                     'Applications" page in LS Central, give it permissions and grant consent. '
                                     + detail) from None
            if exc.code == 403:
                raise LsCentralError(f'The app has no permission to read this data (403): {detail}') from None
            if exc.code == 404:
                raise LsCentralError(f'Not found (404) — check the environment name and company. {detail}') from None
            raise LsCentralError(f'LS Central returned an error ({exc.code}): {detail}') from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, 'reason', exc)
            raise LsCentralError(f'Could not reach LS Central: {reason}') from None
        except ValueError:
            raise LsCentralError('LS Central sent a reply that is not JSON.') from None

    def get(self, path_or_url, params=None):
        url = path_or_url if path_or_url.startswith('http') else f'{self.base}/{path_or_url.lstrip("/")}'
        if params:
            url += ('&' if '?' in url else '?') + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        request = urllib.request.Request(url)
        request.add_header('Authorization', f'Bearer {self._token()}')
        return self._open(request)

    def get_all(self, path, params=None):
        """Every row of a list, following @odata.nextLink pages."""
        data = self.get(path, params)
        rows = list(data.get('value', []))
        while data.get('@odata.nextLink'):
            data = self.get(data['@odata.nextLink'])
            rows.extend(data.get('value', []))
        return rows

    # ── LS Central data ─────────────────────────────────────────────────────

    def companies(self):
        return self.get_all('companies')

    def company_id(self):
        if self._company_id:
            return self._company_id
        companies = self.companies()
        if not companies:
            raise LsCentralError('No companies found in this LS Central environment.')
        wanted = (self.company or '').strip().lower()
        if not wanted:
            if len(companies) > 1:
                names = ', '.join(c.get('name', '') for c in companies)
                raise LsCentralError(f'Several companies found ({names}) — set LS_CENTRAL_COMPANY to one of them.')
            match = companies[0]
        else:
            match = next((c for c in companies if wanted in (
                str(c.get('id', '')).lower(), str(c.get('name', '')).lower(),
                str(c.get('displayName', '')).lower())), None)
            if not match:
                names = ', '.join(c.get('name', '') for c in companies)
                raise LsCentralError(f'Company "{self.company}" not found. Available: {names}')
        self._company_id = match['id']
        return self._company_id

    def web_service(self, name, params=None):
        """Every row of a published ODataV4 web service (these take the company's name, not its id)."""
        if self._company_name is None:
            company_id = self.company_id()
            self._company_name = next(c['name'] for c in self.companies() if c['id'] == company_id)
        company = urllib.parse.quote(self._company_name.replace("'", "''"))
        return self.get_all(f"{self.root}/ODataV4/Company('{company}')/{name}", params)

    def analytics(self, name, params=None):
        """Every row of an entity in the LS Analytics API."""
        return self.get_all(
            f'{self.root}/api/canaryTechnology/lsanalytics/v2.0/companies({self.company_id()})/{name}', params)

    def item(self, item_id):
        """The item card (number, displayName, type, baseUnitOfMeasureCode, gtin, unitPrice, unitCost)."""
        return self.get(f'companies({self.company_id()})/items({item_id})')

    def sales_invoices(self, since):
        """Sales invoices dated on or after `since` (a date), each with its lines."""
        return self.get_all(f'companies({self.company_id()})/salesInvoices', {
            '$filter': f'invoiceDate ge {since.isoformat()}',
            '$expand': 'salesInvoiceLines',
        })

    def sales_invoices_after(self, number):
        """Sales invoices numbered after `number`, whatever their date, each with its lines."""
        quoted = str(number).replace("'", "''")
        return self.get_all(f'companies({self.company_id()})/salesInvoices', {
            '$filter': f"number gt '{quoted}'",
            '$expand': 'salesInvoiceLines',
        })


def _error_text(exc):
    try:
        data = json.loads(exc.read().decode('utf-8'))
    except Exception:
        return ''
    err = data.get('error')
    if isinstance(err, dict):
        return str(err.get('message', ''))[:300]
    return str(data.get('error_description') or err or '')[:300]
