from django import template

register = template.Library()

@register.filter
def user_role(user):
    """Safely get user role, returns empty string if profile doesn't exist."""
    if not user.is_authenticated:
        return ''
    try:
        from inventory.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile.role
    except:
        return ''

@register.filter
def has_role(user, role):
    """Check if user has a specific role."""
    if not user.is_authenticated:
        return False
    try:
        from inventory.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile.role == role
    except:
        return False


@register.simple_tag
def icon(name, cls=''):
    """Inline SVG icon from templates/_icons.html, e.g. {% icon 'truck' %}."""
    from django.utils.html import format_html
    return format_html('<svg class="ic {}" aria-hidden="true" focusable="false"><use href="#i-{}"/></svg>', cls, name)


@register.filter
def num(value, decimals=0):
    """1234567.8 -> '1,234,568' (or with decimals: {{ x|num:2 }}). Blank for missing values."""
    if value in (None, ''):
        return ''
    try:
        return f'{float(value):,.{int(decimals)}f}'
    except (TypeError, ValueError):
        return value


@register.filter
def staff_name(user):
    """Full name, else username; blank when there is no user (e.g. the account was deleted).

    Use instead of ``x.get_full_name|default:x.username``, which raises when x is None.
    """
    if not user:
        return ''
    return user.get_full_name() or user.username
