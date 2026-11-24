from .models import StockAlert
from .navigation import build_menu, can_see, effective_role, ROLE_LABELS, SECTIONS
from .site_access import sees_all_sites, user_sites


def alerts_count(request):
    if request.user.is_authenticated:
        everything = sees_all_sites(request.user)
        return {'open_alerts_count': StockAlert.objects.filter(is_resolved=False).count(),
                'site_label': 'All sites' if everything else ', '.join(user_sites(request.user)) or 'No site assigned'}
    return {'open_alerts_count': 0}


def _item(url_name):
    return next(i for s in SECTIONS for i in s.items if i.url_name == url_name and not i.query)


def navigation(request):
    """Sidebar menu, breadcrumb and header details for base.html."""
    user = request.user
    if not user.is_authenticated:
        return {}
    role = effective_role(user)
    open_alerts = StockAlert.objects.filter(is_resolved=False).count()
    menu, current = build_menu(request, {'open_alerts_count': open_alerts})
    profile = getattr(user, 'profile', None)

    can_alerts = can_see(_item('alert_list'), user, role)
    can_products = can_see(_item('product_list'), user, role)
    return {
        'nav_menu': menu,
        'nav_current': current,   # (section, page label, href) or None
        'nav_role_label': ROLE_LABELS.get(role, 'Inventory System'),
        'nav_role_display': 'Administrator' if user.is_superuser else (profile.get_role_display() if profile else ''),
        'nav_department': profile.get_department_display() if profile else '',
        'nav_can_alerts': can_alerts,
        'nav_alerts': (StockAlert.objects.filter(is_resolved=False).select_related('product')
                       .order_by('-created_at')[:6]) if can_alerts else (),
        'nav_search_url': 'product_list' if can_products else '',
    }
