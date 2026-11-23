from .models import StockAlert
from .site_access import sees_all_sites, user_sites

def alerts_count(request):
    if request.user.is_authenticated:
        everything = sees_all_sites(request.user)
        return {'open_alerts_count': StockAlert.objects.filter(is_resolved=False).count(),
                'site_label': 'All sites' if everything else ', '.join(user_sites(request.user)) or 'No site assigned'}
    return {'open_alerts_count': 0}
