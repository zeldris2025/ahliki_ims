from .models import StockAlert

def alerts_count(request):
    if request.user.is_authenticated:
        return {'open_alerts_count': StockAlert.objects.filter(is_resolved=False).count()}
    return {'open_alerts_count': 0}
