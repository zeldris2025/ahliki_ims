from django.db import migrations


def to_invoice(apps, schema_editor):
    Record = apps.get_model('ls_central', 'LsCentralInvoice')
    Invoice = apps.get_model('inventory', 'Invoice')
    for site in Record.objects.exclude(site='').order_by().values_list('site', flat=True).distinct():
        Invoice.objects.filter(ls_central__site=site).update(site=site)


def to_record(apps, schema_editor):
    Record = apps.get_model('ls_central', 'LsCentralInvoice')
    Invoice = apps.get_model('inventory', 'Invoice')
    for site in Invoice.objects.exclude(site='').order_by().values_list('site', flat=True).distinct():
        Record.objects.filter(invoice__site=site).update(site=site)


class Migration(migrations.Migration):
    """The site now lives on the invoice, so that uploaded invoices can have one too."""

    dependencies = [
        ('ls_central', '0003_lscentralinvoice_site'),
        ('inventory', '0024_site_access'),
    ]

    operations = [
        migrations.RunPython(to_invoice, to_record),
    ]
