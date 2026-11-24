"""The sidebar menu, in one place.

Each link names the roles it is shown to. A link is only shown when the user's role is listed
here *and* the view behind it lets that role in (``role_required`` records its roles on the view
as ``allowed_roles``). So the menu can never offer a page that would bounce the user, and hiding
a link is never the only protection: every view keeps its own ``@role_required``.

Superusers are treated as the Admin role (``role_required`` always lets them in).
"""
from dataclasses import dataclass, field
from functools import lru_cache

from django.urls import NoReverseMatch, resolve, reverse

ADMIN = 'admin'
ALL_ROLES = ('admin', 'manager', 'finance', 'warehouse', 'wms_operator', 'wms_dispatcher',
             'cashier', 'custom_broker')


@dataclass(frozen=True)
class NavItem:
    label: str
    url_name: str
    icon: str
    roles: tuple
    # url_names (or prefixes ending in '*') that mark this link as the current page.
    match: tuple = ()
    # Extra query string, e.g. 'tab=log'. A link with a query only matches when it is present.
    query: str = ''
    staff_only: bool = False   # Django admin pages need is_staff as well
    badge: str = ''            # name of a context value to show as a count


@dataclass(frozen=True)
class NavSection:
    label: str
    items: tuple = field(default_factory=tuple)


CMS = ('admin', 'manager', 'custom_broker')
WMS = ('admin', 'manager', 'warehouse', 'wms_operator')
DISPATCH = ('admin', 'warehouse', 'wms_dispatcher')

SECTIONS = (
    NavSection('Overview', (
        NavItem('Dashboard', 'dashboard', 'dashboard', ('admin', 'manager', 'finance', 'warehouse')),
        NavItem('Operations View', 'manager_dashboard', 'building', ('admin', 'manager')),
        NavItem('WMS Home', 'wms_dashboard', 'home', ('wms_operator',)),
        NavItem('Dispatcher Home', 'wms_dispatcher_dashboard', 'home', ('wms_dispatcher',)),
    )),
    NavSection('Inventory', (
        NavItem('Products', 'product_list', 'package', ('admin', 'manager', 'warehouse', 'finance'),
                match=('product_list', 'product_add', 'product_detail', 'product_edit')),
        NavItem('Categories', 'category_list', 'tag', ('admin', 'manager', 'warehouse'),
                match=('category_*',)),
        NavItem('Suppliers', 'supplier_list', 'factory', ('admin', 'manager', 'warehouse'),
                match=('supplier_*',)),
        NavItem('Stock Lookup', 'stock_lookup', 'search', ('admin', 'manager', 'cashier'),
                match=('stock_lookup*',)),
        NavItem('Stock Movements', 'stock_movements', 'arrows-up-down', ('admin', 'warehouse')),
        NavItem('Stock Adjustments', 'stock_adjust', 'scale', ('admin', 'warehouse')),
        NavItem('Alerts', 'alert_list', 'bell', ('admin', 'manager', 'warehouse'),
                match=('alert_*',), badge='open_alerts_count'),
    )),
    NavSection('Receiving', (
        NavItem('Goods Received', 'grn_list', 'inbox', ('admin', 'warehouse', 'wms_operator'),
                match=('grn_list', 'grn_detail')),
        NavItem('New GRN', 'grn_add', 'plus', ('admin', 'warehouse', 'wms_operator')),
    )),
    NavSection('Warehouse Operations', (
        NavItem('Containers', 'warehouse_container_list', 'container', WMS,
                match=('warehouse_container_list', 'container_check_in', 'container_open',
                       'container_palletize', 'container_close', 'container_reopen',
                       'container_create', 'container_detail', 'container_edit',
                       'container_add_comment')),
        NavItem('Pallets', 'pallet_list', 'layers', WMS, match=('pallet_*',)),
        NavItem('Shelf Locations', 'shelf_list', 'shelves', WMS, match=('shelf_*',)),
        NavItem('Check-in', 'wms_checkin', 'scan', WMS, match=('wms_checkin*',)),
        NavItem('Transfers', 'wms_transfer', 'transfer', WMS),
    )),
    NavSection('Sales & Dispatch', (
        NavItem('Invoice Upload', 'invoice_upload', 'upload', ('admin', 'cashier')),
        NavItem('Invoices', 'invoice_list', 'file-text', ('admin', 'cashier'),
                match=('invoice_list', 'invoice_detail')),
        NavItem('Warehouse Dispatch', 'warehouse_dispatch_list', 'truck', DISPATCH,
                match=('warehouse_dispatch_list', 'warehouse_dispatch_detail',
                       'dispatcher_edit_order', 'picking_ticket')),
        NavItem('Dispatch History', 'warehouse_dispatch_list', 'history', DISPATCH, query='tab=log'),
        NavItem('New Sale (legacy)', 'sale_new', 'cart', ('admin',)),
        NavItem('Sales History (legacy)', 'sale_list', 'receipt', ('admin',),
                match=('sale_list', 'sale_detail')),
    )),
    NavSection('Container Management', (
        NavItem('CMS Dashboard', 'cms_dashboard', 'dashboard', CMS),
        NavItem('Yard Containers', 'cms_containers', 'container', CMS,
                match=('cms_containers', 'cms_container_*')),
        NavItem('Shipping Lines', 'cms_shipping', 'anchor', CMS, match=('cms_shipping*',)),
        NavItem('Returns', 'cms_returns', 'undo', CMS, match=('cms_return*',)),
        NavItem('Atlas Map', 'cms_atlas', 'map', CMS, match=('cms_atlas', 'cms_yard_move')),
        NavItem('CMS Audit Log', 'cms_audit_log', 'shield', CMS),
    )),
    NavSection('Integrations', (
        NavItem('LS Central', 'ls_central:status', 'refresh', ('admin',)),
    )),
    NavSection('Administration', (
        NavItem('Users', 'user_list', 'users', ('admin',), match=('user_*',)),
        NavItem('Reports', 'reports', 'chart', ('admin', 'manager'), match=('reports', 'export_*')),
        NavItem('Audit Log', 'admin:inventory_auditlog_changelist', 'shield', ('admin',),
                staff_only=True),
        NavItem('System Administration', 'admin:index', 'settings', ('admin',), staff_only=True),
    )),
)

ROLE_LABELS = {
    'admin': 'Inventory System', 'manager': 'Operations', 'finance': 'Finance',
    'warehouse': 'Warehouse', 'wms_operator': 'WMS Operator', 'wms_dispatcher': 'WMS Dispatcher',
    'cashier': 'Sales', 'custom_broker': 'Customs Broker',
}


def effective_role(user):
    """The role menus are built for: superusers count as Admin."""
    if not user.is_authenticated:
        return ''
    if user.is_superuser:
        return ADMIN
    profile = getattr(user, 'profile', None)
    return profile.role if profile else ''


@lru_cache(maxsize=None)
def view_roles(url_name):
    """Roles the view behind ``url_name`` admits, or None if it only needs a login."""
    try:
        func = resolve(reverse(url_name)).func
    except NoReverseMatch:
        return frozenset()
    return getattr(func, 'allowed_roles', None)


def can_see(item, user, role):
    if item.staff_only and not user.is_staff:
        return False
    if role not in item.roles:
        return False
    if item.staff_only:
        return True        # Django admin does its own permission checks
    allowed = view_roles(item.url_name)
    return allowed is None or role in allowed or user.is_superuser


def _matches(item, url_name, query):
    if item.query:
        return url_name == item.url_name and item.query in query
    for pattern in (item.match or (item.url_name,)):
        if pattern.endswith('*') and url_name.startswith(pattern[:-1]):
            return True
        if url_name == pattern:
            return True
    return False


def build_menu(request, context=None):
    """[{'label', 'items': [{'label', 'href', 'icon', 'active', 'badge'}]}] for this user."""
    user = request.user
    role = effective_role(user)
    match = getattr(request, 'resolver_match', None)
    url_name = ''
    if match:
        url_name = f'{match.namespace}:{match.url_name}' if match.namespace else (match.url_name or '')
    query = request.GET.urlencode()
    context = context or {}

    menu, current = [], None
    for section in SECTIONS:
        items = []
        for item in section.items:
            if not can_see(item, user, role):
                continue
            items.append({'label': item.label, 'icon': item.icon,
                          'href': reverse(item.url_name) + (f'?{item.query}' if item.query else ''),
                          'active': False, 'badge': context.get(item.badge) if item.badge else None,
                          '_item': item})
        if not items:
            continue
        # Most specific match wins (a link with a query beats the same page without one).
        hits = [i for i in items if _matches(i['_item'], url_name, query)]
        if hits and current is None:
            best = max(hits, key=lambda i: bool(i['_item'].query))
            best['active'] = True
            current = (section.label, best['label'], best['href'])
        for i in items:
            del i['_item']
        menu.append({'label': section.label, 'items': items,
                     'open': any(i['active'] for i in items)})
    return menu, current
