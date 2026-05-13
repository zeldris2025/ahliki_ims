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
