from django.conf import settings
from django.db import models


class LsCentralInvoice(models.Model):
    """Links an invoice in Warehouse Dispatch to the LS Central invoice it was imported from."""

    invoice = models.OneToOneField('inventory.Invoice', on_delete=models.CASCADE, related_name='ls_central')
    ls_id = models.CharField('LS Central id', max_length=64, unique=True)
    ls_number = models.CharField('LS Central number', max_length=100)
    ls_status = models.CharField(max_length=30, blank=True)
    invoice_date = models.DateField(null=True, blank=True)
    # Lines that could not be matched to a product in the catalogue, as LS Central sent them.
    unmatched_lines = models.JSONField(default=list, blank=True)
    linked_existing = models.BooleanField(default=False,
                                          help_text='The invoice was already in the system (e.g. uploaded as a PDF) '
                                                    'and was linked instead of imported again.')
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-imported_at']
        verbose_name = 'LS Central invoice'

    def __str__(self):
        return self.ls_number


class LsCentralSync(models.Model):
    """One run of the invoice import, for the status page."""

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    imported = models.PositiveIntegerField(default=0)
    updated = models.PositiveIntegerField(default=0)
    unmatched_lines = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        verbose_name = 'LS Central sync'

    def __str__(self):
        return f'{self.started_at:%Y-%m-%d %H:%M} — {"ok" if self.ok else "failed"}'
