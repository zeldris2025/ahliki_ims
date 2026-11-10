from django.contrib import admin

from .models import Enquiry


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('name', 'topic', 'level', 'email', 'phone', 'created_at', 'handled')
    list_filter = ('handled', 'topic', 'level')
    list_editable = ('handled',)
    search_fields = ('name', 'email', 'phone', 'message')
    readonly_fields = ('created_at',)
