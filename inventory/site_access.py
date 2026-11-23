"""Site access levels: who may see which invoices.

* Superusers and the Admin role see every site, and invoices that have no site.
* Everyone else sees only invoices of the sites ticked for them on the Users page. None ticked
  means no invoices.

Anything that shows or changes an invoice must get it through visible_invoices() or
get_visible_invoice(), never straight from Invoice.objects. An invoice of another site is "not
found", so its existence isn't given away either.
"""
from django.shortcuts import get_object_or_404

from .models import SITES, Invoice, UserProfile


def sees_all_sites(user):
    if not (user.is_authenticated and user.is_active):
        return False
    return user.is_superuser or UserProfile.objects.filter(user=user, role='admin').exists()


def user_sites(user):
    """The sites this user may work with, in the standard order."""
    if not (user.is_authenticated and user.is_active):
        return []
    if user.is_superuser:
        return list(SITES)
    profile = UserProfile.objects.filter(user=user).first()
    if not profile:
        return []
    return list(SITES) if profile.role == 'admin' else profile.site_list


def visible_invoices(user):
    if sees_all_sites(user):
        return Invoice.objects.all()
    return Invoice.objects.filter(site__in=user_sites(user))


def get_visible_invoice(user, **lookup):
    return get_object_or_404(visible_invoices(user), **lookup)


def mask_other_sites(user, movements):
    """Stock is shared, so every movement is listed, but not another site's invoice number."""
    movements = list(movements)
    if sees_all_sites(user):
        return movements
    references = {m.reference for m in movements if m.reference}
    hidden = set(Invoice.objects.filter(invoice_number__in=references)
                 .exclude(pk__in=visible_invoices(user).values('pk'))
                 .values_list('invoice_number', flat=True))
    for movement in movements:
        if movement.reference in hidden:
            movement.reference = 'Invoice at another site'
    return movements
