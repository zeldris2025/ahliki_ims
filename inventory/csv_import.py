import csv
import io

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse


class CSVImportMixin:
    """Adds an 'Import CSV' button + downloadable template to a ModelAdmin.

    Subclasses declare:
        csv_columns       — list of (column_name, required, help_text)
        csv_sample_rows   — list of rows (aligned to csv_columns) for the template file
    and implement import_csv_row(row) -> 'created' | 'updated'.
    """
    change_list_template = 'admin/csv_import_change_list.html'
    csv_columns = []
    csv_sample_rows = []

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        return [
            path('import-csv/', self.admin_site.admin_view(self.import_csv_view),
                 name='%s_%s_import_csv' % info),
            path('import-csv/template/', self.admin_site.admin_view(self.csv_template_view),
                 name='%s_%s_csv_template' % info),
        ] + super().get_urls()

    # ── template download ────────────────────────────────────────────────────

    def csv_template_view(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename="%s_template.csv"' % self.model._meta.model_name
        )
        writer = csv.writer(response)
        writer.writerow([c[0] for c in self.csv_columns])
        for row in self.csv_sample_rows:
            writer.writerow(row)
        return response

    # ── upload + import ──────────────────────────────────────────────────────

    def import_csv_view(self, request):
        info = self.model._meta.app_label, self.model._meta.model_name
        changelist_url = reverse('admin:%s_%s_changelist' % info)

        if request.method == 'POST':
            upload = request.FILES.get('csv_file')
            if not upload:
                self.message_user(request, 'Please choose a CSV file.', messages.ERROR)
                return redirect(request.path)
            if not upload.name.lower().endswith('.csv'):
                self.message_user(request, 'File must be a .csv file.', messages.ERROR)
                return redirect(request.path)

            try:
                text = upload.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                self.message_user(request, 'Could not read the file — save it as UTF-8 CSV.',
                                  messages.ERROR)
                return redirect(request.path)

            reader = csv.DictReader(io.StringIO(text))
            headers = [h.strip() for h in (reader.fieldnames or [])]
            required = [c[0] for c in self.csv_columns if c[1]]
            missing = [c for c in required if c not in headers]
            if missing:
                self.message_user(request, 'Missing required column(s): %s' % ', '.join(missing),
                                  messages.ERROR)
                return redirect(request.path)

            created = updated = 0
            errors = []
            for line_no, raw in enumerate(reader, start=2):
                row = {(k or '').strip(): (v or '').strip() for k, v in raw.items()}
                if not any(row.values()):
                    continue
                try:
                    result = self.import_csv_row(row)
                except Exception as exc:
                    errors.append('Row %d: %s' % (line_no, exc))
                    continue
                if result == 'created':
                    created += 1
                elif result == 'updated':
                    updated += 1

            if created or updated:
                self.message_user(
                    request, 'Import finished — %d created, %d updated.' % (created, updated),
                    messages.SUCCESS)
            for err in errors[:20]:
                self.message_user(request, err, messages.ERROR)
            if len(errors) > 20:
                self.message_user(request, '…and %d more row error(s).' % (len(errors) - 20),
                                  messages.ERROR)
            if not created and not updated and not errors:
                self.message_user(request, 'No rows found in the file.', messages.WARNING)

            if errors:
                return redirect(request.path)
            return redirect(changelist_url)

        context = {
            **self.admin_site.each_context(request),
            'title': 'Import %s from CSV' % self.model._meta.verbose_name_plural,
            'opts': self.model._meta,
            'csv_columns': self.csv_columns,
            'template_url': reverse('admin:%s_%s_csv_template' % info),
            'changelist_url': changelist_url,
        }
        return TemplateResponse(request, 'admin/csv_import.html', context)

    def import_csv_row(self, row):  # pragma: no cover - subclass responsibility
        raise NotImplementedError


def to_decimal(value, default='0'):
    from decimal import Decimal, InvalidOperation
    value = (value or '').replace(',', '').strip()
    if not value:
        value = default
    try:
        return Decimal(value)
    except InvalidOperation:
        raise ValueError('"%s" is not a valid number' % value)


def to_int(value, default=0):
    value = (value or '').replace(',', '').strip()
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        raise ValueError('"%s" is not a valid whole number' % value)


def to_bool(value, default=True):
    value = (value or '').strip().lower()
    if not value:
        return default
    return value in ('1', 'true', 'yes', 'y', 'active')
