from django import template

from ..client import is_configured
from ..models import LsCentralSync
from ..views import is_ls_admin

register = template.Library()


@register.inclusion_tag('ls_central/_dispatch_bar.html', takes_context=True)
def ls_central_bar(context):
    """Sync button and last-sync line for the Warehouse Dispatch page."""
    request = context.get('request')
    return {
        'configured': is_configured(),
        'last': LsCentralSync.objects.first(),
        'request': request,
        'csrf_token': context.get('csrf_token'),
        'can_configure': bool(request) and is_ls_admin(request.user),
    }
