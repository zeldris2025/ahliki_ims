from django.contrib import admin

from inventory.site_access import visible_invoices

from .models import LsCentralInvoice, LsCentralSync


@admin.register(LsCentralInvoice)
class LsCentralInvoiceAdmin(admin.ModelAdmin):
    list_display = ('ls_number', 'invoice', 'ls_status', 'invoice_date', 'linked_existing', 'imported_at')
    list_filter = ('ls_status', 'linked_existing')
    search_fields = ('ls_number', 'ls_id', 'invoice__customer_name')
    readonly_fields = ('invoice', 'ls_id', 'ls_number', 'imported_at')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(invoice__in=visible_invoices(request.user))


@admin.register(LsCentralSync)
class LsCentralSyncAdmin(admin.ModelAdmin):
    list_display = ('started_at', 'ok', 'imported', 'updated', 'unmatched_lines', 'triggered_by', 'message')
    list_filter = ('ok',)
