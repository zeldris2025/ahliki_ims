"""CMS — Container Management System for the customs broker.

Containers sitting in yards around Upolu, the shipping lines that own them and
their return deadlines, the history of boxes returned to the wharf, and the
Ah Liki Atlas map of every yard.
"""
import json
from collections import Counter
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, Count, IntegerField, ProtectedError, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import cms_csv
from .forms import CmsContainerForm, ContainerReturnForm, ContainerTransferForm, ShippingLineForm
from .models import CmsContainer, ContainerReturn, ShippingLine, Yard
from .views import role_required

CMS_ROLES = ('admin', 'manager', 'custom_broker')
PAGE_SIZE = 50
OWN_OWNER = 'ALW'   # Ah Liki's own containers
IMPORT_SESSION_KEY = 'cms_import_csv'

SORTS = {
    'code': 'code', '-code': '-code',
    'arrival': 'arrival_date', '-arrival': '-arrival_date',
    'yard': 'yard__sort_order', '-yard': '-yard__sort_order',
    'owner': 'owner__name', '-owner': '-owner__name',
    'status': 'status', '-status': '-status',
}


def _staff_name(user):
    return user.get_full_name() or user.username


def _safe_next(request, default):
    nxt = request.POST.get('next') or request.GET.get('next') or ''
    return nxt if nxt.startswith('/') and not nxt.startswith('//') else reverse(default)


def _drivers():
    """Every driver name used so far — offered as suggestions in driver fields."""
    names = set(CmsContainer.objects.exclude(driver='').values_list('driver', flat=True))
    names |= set(ContainerReturn.objects.exclude(driver='').values_list('driver', flat=True))
    return sorted(names, key=str.lower)


def _due_q(kind):
    """Q for containers whose return is overdue ('overdue') or due within 7 days ('week').
    Deadlines are arrival date + the owner's return days, so build one clause per owner."""
    today = timezone.localdate()
    q = Q(pk__in=[])
    for owner in ShippingLine.objects.filter(return_days__isnull=False):
        overdue_before = today - timedelta(days=owner.return_days)
        if kind == 'overdue':
            q |= Q(owner=owner, arrival_date__lt=overdue_before)
        else:
            q |= Q(owner=owner, arrival_date__gte=overdue_before,
                   arrival_date__lte=overdue_before + timedelta(days=7))
    return q


def _active_stats():
    active = CmsContainer.objects.filter(returned=False)
    by_status = dict(active.values_list('status').annotate(n=Count('pk')))
    month_start = timezone.localdate().replace(day=1)
    return {
        'active': active.count(),
        'wharf': active.filter(yard__code=Yard.WHARF).count(),
        'full': by_status.get(CmsContainer.STATUS_FULL, 0),
        'storage': by_status.get(CmsContainer.STATUS_STORAGE, 0),
        'empty': by_status.get(CmsContainer.STATUS_EMPTY, 0),
        'overdue': active.filter(_due_q('overdue')).count(),
        'due_week': active.filter(_due_q('week')).count(),
        'returned_month': ContainerReturn.objects.filter(
            Q(returned_date__gte=month_start) | Q(returned_date__isnull=True, created_at__date__gte=month_start)
        ).count(),
        'returned_total': ContainerReturn.objects.count(),
    }


# ── Dashboard ────────────────────────────────────────────────────────────────

def _dashboard_years(request, today):
    """Years offered in the dashboard's year picker, and the one chosen (?year=, else this year).
    Runs from the first year on record to next year, so the default rolls over on 1 January."""
    first = CmsContainer.objects.filter(arrival_date__isnull=False).order_by('arrival_date') \
        .values_list('arrival_date', flat=True).first()
    years = list(range(min(first.year if first else today.year, today.year), today.year + 2))
    picked = request.GET.get('year', '')
    year = int(picked) if picked.isdigit() and int(picked) in years else today.year
    return years[::-1], year


@login_required
@role_required(*CMS_ROLES)
def dashboard(request):
    active = CmsContainer.objects.filter(returned=False).select_related('yard', 'owner')
    today = timezone.localdate()
    years, year = _dashboard_years(request, today)
    year_start = date(year, 1, 1)
    history_end = min(date(year, 12, 31), today)   # charts of past events stop at today

    # Containers per yard, split by status (stacked bar).
    per_yard = {}
    for yard_id, status, n in active.values_list('yard_id', 'status').annotate(n=Count('pk')):
        per_yard.setdefault(yard_id, Counter())[status] = n
    yards = [y for y in Yard.objects.all() if y.is_active or y.pk in per_yard]
    yard_chart = {
        'labels': [y.code for y in yards],
        'ids': [y.pk for y in yards],
        'series': [{'key': key, 'label': label,
                    'data': [per_yard.get(y.pk, Counter())[key] for y in yards]}
                   for key, label in CmsContainer.STATUS_CHOICES],
    }

    owners = ShippingLine.objects.annotate(n=Count('containers', filter=Q(containers__returned=False)))
    owner_chart = {'labels': [o.name for o in owners], 'ids': [o.pk for o in owners],
                   'data': [o.n for o in owners]}

    # When each visit left for the wharf: its return date, else the day the return was recorded.
    left_on = {}
    for cid, d, created in ContainerReturn.objects.values_list('container_id', 'returned_date', 'created_at'):
        d = d or timezone.localdate(created)
        left_on[cid] = max(left_on.get(cid, d), d)

    # Flow per month of the chosen year: boxes in by A/Date vs boxes back to the wharf.
    arrived, returned = Counter(), Counter()
    for d in CmsContainer.objects.filter(arrival_date__gte=year_start, arrival_date__lte=history_end) \
            .values_list('arrival_date', flat=True):
        arrived[d.month - 1] += 1
    for d in left_on.values():
        if year_start <= d <= history_end:
            returned[d.month - 1] += 1
    months = 12 if year < today.year else (today.month if year == today.year else 0)
    flow_chart = {'labels': [date(year, m, 1).strftime('%b') for m in range(1, months + 1)],
                  'arrived': [arrived[i] for i in range(months)],
                  'returned': [returned[i] for i in range(months)]}

    # Boxes in yards on each day of the chosen year (up to today), rebuilt from arrival and return dates.
    days = max((history_end - year_start).days + 1, 0)
    delta = Counter()
    for pk, arrival, is_returned in CmsContainer.objects.filter(arrival_date__isnull=False,
                                                                arrival_date__lte=history_end) \
            .values_list('pk', 'arrival_date', 'returned'):
        gone = left_on.get(pk) if is_returned else None
        if is_returned and gone is None:
            continue    # returned with no date on record — can't place it in time
        if gone is not None and gone <= year_start:
            continue
        delta[max((arrival - year_start).days, 0)] += 1
        if gone is not None:
            delta[(gone - year_start).days] -= 1
    level, series = 0, []
    for i in range(days):
        level += delta[i]
        series.append(level)
    occupancy_chart = {'labels': [(year_start + timedelta(days=i)).strftime('%d %b') for i in range(days)],
                       'undated': active.filter(arrival_date__isnull=True).count(),
                       'data': series}

    # Return runway: active boxes bucketed by days until (or past) their deadline.
    runway_buckets = [('>30d late', -10**6, -31), ('15–30d late', -30, -15), ('8–14d late', -14, -8),
                      ('1–7d late', -7, -1), ('Due ≤7d', 0, 7), ('8–14d', 8, 14),
                      ('15–30d', 15, 30), ('30d+', 31, 10**6)]
    runway = Counter()
    no_deadline = 0
    for c in active:
        left = c.days_left
        if left is None:
            no_deadline += 1
            continue
        for label, lo, hi in runway_buckets:
            if lo <= left <= hi:
                runway[label] += 1
                break
    runway_chart = {'labels': [b[0] for b in runway_buckets],
                    'data': [runway[b[0]] for b in runway_buckets],
                    'no_deadline': no_deadline}

    # Yard × owner matrix for the heatmap.
    cells = Counter({(y, o): n for y, o, n in
                     active.values_list('yard_id', 'owner_id').annotate(n=Count('pk'))})
    heat_owners = [o for o in owners if o.n]
    heat_yards = [y for y in yards if any(cells[(y.pk, o.pk)] for o in heat_owners)]
    heatmap = {'yards': [{'id': y.pk, 'code': y.code} for y in heat_yards],
               'owners': [{'id': o.pk, 'name': o.name} for o in heat_owners],
               'cells': [[cells[(y.pk, o.pk)] for o in heat_owners] for y in heat_yards]}

    # Return deadlines: overdue plus anything due in the next 14 days, most urgent first.
    due_soon = [c for c in active.filter(arrival_date__isnull=False, owner__return_days__isnull=False)
                if c.days_left is not None and c.days_left <= 14]
    due_soon.sort(key=lambda c: (c.days_left, c.code))

    # Return calendar: every box in a yard keyed by the day it is due back.
    due_calendar = {}
    for c in active:
        due = c.return_due
        if due is not None:
            due_calendar.setdefault(due.isoformat(), []).append(
                {'id': c.pk, 'code': c.code, 'owner': c.owner.name, 'yard': c.yard.code})

    chart_json = json.dumps({'yards': yard_chart, 'owners': owner_chart, 'flow': flow_chart,
                             'occupancy': occupancy_chart, 'runway': runway_chart, 'heatmap': heatmap,
                             'due_calendar': due_calendar, 'today': today.isoformat(), 'year': year,
                             'edit_url': reverse('cms_container_edit', args=[0]),
                             'containers_url': reverse('cms_containers')}).replace('<', '\\u003c')
    return render(request, 'cms/dashboard.html', {
        'stats': _active_stats(),
        'chart_json': chart_json,
        'due_soon': due_soon[:25],
        'due_soon_total': len(due_soon),
        'recent_returns': ContainerReturn.objects.filter(
            Q(returned_date__year=year) | Q(returned_date__isnull=True, created_at__year=year)
        ).select_related('container', 'yard')[:6],
        'year': year,
        'years': years,
        'no_deadlines': not ShippingLine.objects.filter(return_days__isnull=False).exists(),
        'today': today,
        'staff_name': _staff_name(request.user),
        'drivers': _drivers(),
    })


# ── Containers ───────────────────────────────────────────────────────────────

def _filtered_containers(params):
    qs = CmsContainer.objects.select_related('yard', 'owner')
    f = {k: params.get(k, '').strip() for k in
         ('q', 'yard', 'status', 'owner', 'returned', 'due', 'from', 'to', 'sort')}
    f['returned'] = f['returned'] or 'no'
    if f['q']:
        for word in f['q'].split():
            qs = qs.filter(Q(code__icontains=word) | Q(description__icontains=word) |
                           Q(vessel_voyage__icontains=word) | Q(note__icontains=word) |
                           Q(driver__icontains=word))
    if f['yard'].isdigit():
        qs = qs.filter(yard_id=f['yard'])
    if f['status'] in dict(CmsContainer.STATUS_CHOICES):
        qs = qs.filter(status=f['status'])
    if f['owner'].isdigit():
        qs = qs.filter(owner_id=f['owner'])
    if f['returned'] == 'no':
        qs = qs.filter(returned=False)
    elif f['returned'] == 'yes':
        qs = qs.filter(returned=True)
    if f['due'] in ('overdue', 'week'):
        qs = qs.filter(_due_q(f['due']), returned=False)
    for key, lookup in (('from', 'arrival_date__gte'), ('to', 'arrival_date__lte')):
        try:
            qs = qs.filter(**{lookup: date.fromisoformat(f[key])})
        except ValueError:
            f[key] = ''
    # Ah Liki's own (ALW) boxes always go to the end of the list, whatever the sort.
    own_last = Case(When(owner__name__iexact=OWN_OWNER, then=Value(1)), default=Value(0),
                    output_field=IntegerField())
    qs = qs.order_by(own_last, SORTS.get(f['sort'], 'arrival_date'), 'code')
    return qs, f


@login_required
@role_required(*CMS_ROLES)
def container_list(request):
    qs, f = _filtered_containers(request.GET)
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="containers_{timezone.localdate():%Y%m%d}.csv"'
        cms_csv.write_containers(response, qs)
        return response

    page = Paginator(qs.annotate(n_transfers=Count('transfers')), PAGE_SIZE).get_page(request.GET.get('page'))
    params = request.GET.copy()
    params.pop('page', None)
    sort_params = params.copy()
    sort_params.pop('sort', None)
    active_filters = sum(1 for k in ('yard', 'status', 'owner', 'due', 'from', 'to') if f[k]) + \
        (f['returned'] != 'no')

    # Quick-filter buttons under the heading: In Yards, Wharf, Empty, Storage, Overdue.
    wharf = Yard.objects.filter(code=Yard.WHARF).first()
    if f['returned'] == 'no' and active_filters == 0:
        tile = 'yards'
    elif active_filters == 1 and wharf and f['yard'] == str(wharf.pk):
        tile = 'wharf'
    elif active_filters == 1 and f['status'] in (CmsContainer.STATUS_EMPTY, CmsContainer.STATUS_STORAGE):
        tile = f['status']
    elif active_filters == 1 and f['due'] == 'overdue':
        tile = 'overdue'
    elif active_filters == 1 and f['returned'] == 'yes':
        tile = 'returned'
    else:
        tile = ''
    return render(request, 'cms/containers.html', {
        'tile': tile,
        'wharf': wharf,
        'page': page,
        'f': f,
        'query': params.urlencode(),
        'sort_query': sort_params.urlencode(),
        'active_filters': active_filters,
        'stats': _active_stats(),
        'yards': Yard.objects.all(),
        'active_yards': Yard.objects.filter(is_active=True),
        'owners': ShippingLine.objects.all(),
        'status_choices': CmsContainer.STATUS_CHOICES,
        'today': timezone.localdate(),
        'staff_name': _staff_name(request.user),
        'drivers': _drivers(),
    })


@login_required
@role_required(*CMS_ROLES)
def container_add(request):
    initial = {'arrival_date': timezone.localdate()}
    if request.GET.get('yard', '').isdigit():
        initial['yard'] = request.GET['yard']
    form = CmsContainerForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        container = form.save(commit=False)
        container.created_by = request.user
        container.save()
        messages.success(request, f'{container.code} added to {container.yard}.')
        if 'save_another' in request.POST:
            return redirect(f"{reverse('cms_container_add')}?yard={container.yard_id}")
        return redirect('cms_containers')
    return render(request, 'cms/container_form.html', {'form': form, 'container': None, 'drivers': _drivers(),
                                                       'next': ''})


@login_required
@role_required(*CMS_ROLES)
def container_edit(request, pk):
    container = get_object_or_404(CmsContainer.objects.select_related('yard', 'owner'), pk=pk)
    form = CmsContainerForm(request.POST or None, instance=container)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'{container.code} updated.')
        return redirect(_safe_next(request, 'cms_containers'))
    history = CmsContainer.objects.filter(code=container.code).exclude(pk=pk) \
        .select_related('yard', 'owner').prefetch_related('returns')
    return render(request, 'cms/container_form.html', {
        'form': form,
        'container': container,
        'history': history,
        'returns': container.returns.select_related('yard'),
        'transfers': list(container.transfers.select_related('from_yard', 'to_yard')),
        'active_yards': Yard.objects.filter(is_active=True),
        'return_form': ContainerReturnForm(initial={'returned_date': timezone.localdate(),
                                                    'staff_name': _staff_name(request.user)}),
        'next': _safe_next(request, 'cms_containers') if request.GET.get('next') else '',
        'drivers': _drivers(),
        'today': timezone.localdate(),
        'staff_name': _staff_name(request.user),
    })


@login_required
@role_required(*CMS_ROLES)
@require_POST
def container_delete(request, pk):
    container = get_object_or_404(CmsContainer, pk=pk)
    container.delete()
    messages.success(request, f'{container.code} deleted.')
    return redirect(_safe_next(request, 'cms_containers'))


@login_required
@role_required(*CMS_ROLES)
@require_POST
def container_transfer(request, pk):
    """Move a container to another yard. Every transfer is recorded, so the whole trail stays visible."""
    container = get_object_or_404(CmsContainer.objects.select_related('yard'), pk=pk)
    form = ContainerTransferForm(request.POST)
    if container.returned:
        messages.warning(request, f'{container.code} has been returned to the wharf and cannot be transferred.')
    elif not form.is_valid():
        messages.error(request, 'Pick the yard to transfer to and the date.')
    elif form.cleaned_data['to_yard'].pk == container.yard_id:
        messages.warning(request, f'{container.code} is already in {container.yard}.')
    else:
        d = form.cleaned_data
        from_yard = container.yard
        cms_csv.transfer(container, d['to_yard'], d['transferred_date'], d['driver'].strip(),
                         d['staff_name'].strip(), d['note'].strip(), request.user)
        messages.success(request, f'{container.code} transferred from {from_yard} to {d["to_yard"]}.')
    return redirect(_safe_next(request, 'cms_containers'))


@login_required
@role_required(*CMS_ROLES)
@require_POST
def container_return(request, pk):
    container = get_object_or_404(CmsContainer, pk=pk)
    form = ContainerReturnForm(request.POST)
    if container.returned:
        messages.warning(request, f'{container.code} has already been returned.')
    elif not form.is_valid():
        messages.error(request, 'Enter the returned date and staff name.')
    else:
        cms_csv.mark_returned(container, form.cleaned_data['returned_date'],
                              form.cleaned_data['staff_name'].strip(), form.cleaned_data['driver'].strip(),
                              request.user)
        messages.success(request, f'{container.code} returned to the wharf.')
    return redirect(_safe_next(request, 'cms_containers'))


@login_required
@role_required(*CMS_ROLES)
@require_POST
def container_bulk(request):
    ids = [i for i in request.POST.getlist('ids') if i.isdigit()]
    action = request.POST.get('action')
    containers = CmsContainer.objects.filter(pk__in=ids)
    nxt = _safe_next(request, 'cms_containers')
    if not ids:
        messages.warning(request, 'Tick at least one container first.')
        return redirect(nxt)

    if action == 'move':
        yard = Yard.objects.filter(pk=request.POST.get('yard') or 0).first()
        if not yard:
            messages.error(request, 'Pick a yard to move the containers to.')
        else:
            moving = [c for c in containers.filter(returned=False).select_related('yard') if c.yard_id != yard.pk]
            with transaction.atomic():
                for c in moving:   # logged as transfers, like the Transfer button
                    cms_csv.transfer(c, yard, timezone.localdate(), '', _staff_name(request.user),
                                     'Bulk move', request.user)
            messages.success(request, f'Moved {len(moving)} container(s) to {yard}.')
    elif action == 'status':
        status = request.POST.get('status')
        if status not in dict(CmsContainer.STATUS_CHOICES):
            messages.error(request, 'Pick a status.')
        else:
            n = containers.filter(returned=False).update(status=status, updated_at=timezone.now())
            messages.success(request, f'Set {n} container(s) to {dict(CmsContainer.STATUS_CHOICES)[status]}.')
    elif action == 'return':
        form = ContainerReturnForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Enter the returned date and staff name.')
        else:
            with transaction.atomic():
                todo = list(containers.filter(returned=False).select_related('yard'))
                for c in todo:
                    cms_csv.mark_returned(c, form.cleaned_data['returned_date'],
                                          form.cleaned_data['staff_name'].strip(),
                                          form.cleaned_data['driver'].strip(), request.user)
            messages.success(request, f'Returned {len(todo)} container(s) to the wharf.')
    elif action == 'delete':
        n = containers.count()
        containers.delete()
        messages.success(request, f'Deleted {n} container(s).')
    else:
        messages.error(request, 'Unknown action.')
    return redirect(nxt)


# ── CSV import ───────────────────────────────────────────────────────────────

@login_required
@role_required(*CMS_ROLES)
def container_import(request):
    if request.method == 'POST' and request.POST.get('confirm'):
        text = request.session.get(IMPORT_SESSION_KEY)
        if not text:
            messages.error(request, 'The upload expired — choose the file again.')
            return redirect('cms_container_import')
        rows, errors = cms_csv.parse(text)
        if not rows:
            messages.error(request, 'Nothing to import.')
            return redirect('cms_container_import')
        counts = cms_csv.apply(rows, request.user)
        del request.session[IMPORT_SESSION_KEY]
        parts = [f"{counts['created']} added", f"{counts['updated']} updated"]
        if counts['returned']:
            parts.append(f"{counts['returned']} marked returned")
        if counts['skipped']:
            parts.append(f"{counts['skipped']} already in returned history")
        if errors:
            parts.append(f'{len(errors)} row(s) with errors skipped')
        messages.success(request, 'Import complete — ' + ', '.join(parts) + '.')
        return redirect('cms_containers')

    context = {'columns': cms_csv.COLUMNS, 'yards': Yard.objects.filter(is_active=True),
               'owners': ShippingLine.objects.all()}
    if request.method == 'POST':
        upload = request.FILES.get('file')
        try:
            if not upload:
                raise cms_csv.ImportError_('Choose a CSV file to upload.')
            if not upload.name.lower().endswith(('.csv', '.txt')):
                raise cms_csv.ImportError_('That is not a CSV file. In Excel use File → Save As → "CSV UTF-8".')
            text = cms_csv.decode(upload.read())
            rows, errors = cms_csv.parse(text)
        except cms_csv.ImportError_ as e:
            context['file_error'] = str(e)
        else:
            request.session[IMPORT_SESSION_KEY] = text
            context.update({
                'filename': upload.name,
                'rows': rows,
                'errors': errors,
                'new_count': sum(1 for r in rows if not r['existing_id']),
                'update_count': sum(1 for r in rows if r['existing_id']),
                'returned_count': sum(1 for r in rows if r['returned']),
            })
    return render(request, 'cms/import.html', context)


@login_required
@role_required(*CMS_ROLES)
def container_import_template(request):
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="containers_template.csv"'
    writer = csv.writer(response)
    writer.writerow(cms_csv.COLUMNS)
    writer.writerows(cms_csv.SAMPLE_ROWS)
    return response


# ── Shipping lines ───────────────────────────────────────────────────────────

@login_required
@role_required(*CMS_ROLES)
def shipping(request, pk=None):
    line = get_object_or_404(ShippingLine, pk=pk) if pk else None
    form = ShippingLineForm(request.POST or None, instance=line)
    if request.method == 'POST' and form.is_valid():
        saved = form.save()
        messages.success(request, f'{saved.name} {"updated" if line else "added"}.')
        return redirect('cms_shipping')

    lines = ShippingLine.objects.annotate(
        active=Count('containers', filter=Q(containers__returned=False)),
        total=Count('containers'),
    )
    overdue = Counter(CmsContainer.objects.filter(_due_q('overdue'), returned=False)
                      .values_list('owner_id', flat=True))
    due_week = Counter(CmsContainer.objects.filter(_due_q('week'), returned=False)
                       .values_list('owner_id', flat=True))
    for sl in lines:
        sl.overdue = overdue.get(sl.pk, 0)
        sl.due_week = due_week.get(sl.pk, 0)
    return render(request, 'cms/shipping.html', {'form': form, 'editing': line, 'lines': lines})


@login_required
@role_required(*CMS_ROLES)
@require_POST
def shipping_delete(request, pk):
    line = get_object_or_404(ShippingLine, pk=pk)
    try:
        line.delete()
        messages.success(request, f'{line.name} deleted.')
    except ProtectedError:
        messages.error(request, f'{line.name} still owns containers — it cannot be deleted.')
    return redirect('cms_shipping')


# ── Returned containers ──────────────────────────────────────────────────────

@login_required
@role_required(*CMS_ROLES)
def returns(request):
    qs = ContainerReturn.objects.select_related('container', 'yard', 'recorded_by')
    f = {k: request.GET.get(k, '').strip() for k in ('q', 'yard', 'status', 'from', 'to')}
    if f['q']:
        for word in f['q'].split():
            qs = qs.filter(Q(container__code__icontains=word) | Q(description__icontains=word) |
                           Q(staff_name__icontains=word) | Q(driver__icontains=word))
    if f['yard'].isdigit():
        qs = qs.filter(yard_id=f['yard'])
    if f['status'] in dict(CmsContainer.STATUS_CHOICES):
        qs = qs.filter(status=f['status'])
    for key, lookup in (('from', 'returned_date__gte'), ('to', 'returned_date__lte')):
        try:
            qs = qs.filter(**{lookup: date.fromisoformat(f[key])})
        except ValueError:
            f[key] = ''

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="returned_{timezone.localdate():%Y%m%d}.csv"'
        cms_csv.write_returns(response, qs)
        return response

    params = request.GET.copy()
    params.pop('page', None)
    today = timezone.localdate()
    return render(request, 'cms/returns.html', {
        'page': Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page')),
        'f': f,
        'query': params.urlencode(),
        'yards': Yard.objects.all(),
        'status_choices': CmsContainer.STATUS_CHOICES,
        'count_total': ContainerReturn.objects.count(),
        'count_month': ContainerReturn.objects.filter(returned_date__gte=today.replace(day=1)).count(),
        'count_week': ContainerReturn.objects.filter(returned_date__gte=today - timedelta(days=6)).count(),
    })


@login_required
@role_required(*CMS_ROLES)
@require_POST
def return_undo(request, pk):
    record = get_object_or_404(ContainerReturn.objects.select_related('container'), pk=pk)
    container = record.container
    if CmsContainer.objects.filter(code=container.code, returned=False).exclude(pk=container.pk).exists():
        messages.error(request, f'{container.code} is already back in a yard on a later voyage — '
                                f'this return cannot be undone.')
        return redirect(_safe_next(request, 'cms_returns'))
    with transaction.atomic():
        record.delete()
        if not container.returns.exists():
            container.returned = False
            container.save(update_fields=['returned', 'updated_at'])
    messages.success(request, f'Return of {container.code} undone — it is back in {container.yard}.')
    return redirect(_safe_next(request, 'cms_returns'))


# ── Ah Liki Atlas ────────────────────────────────────────────────────────────

def _atlas_payload():
    yards = {y.pk: {
        'id': y.pk, 'code': y.code, 'description': y.description, 'lat': y.latitude, 'lng': y.longitude,
        'total': 0, 'full': 0, 'storage': 0, 'empty': 0, 'overdue': 0, 'due_week': 0,
        'owners': Counter(), 'containers': [],
        'list_url': f"{reverse('cms_containers')}?yard={y.pk}",
        'add_url': f"{reverse('cms_container_add')}?yard={y.pk}",
        'move_url': reverse('cms_yard_move', args=[y.pk]),
    } for y in Yard.objects.all()}
    for c in CmsContainer.objects.filter(returned=False).select_related('owner').order_by('arrival_date', 'code'):
        y = yards[c.yard_id]
        y['total'] += 1
        y[c.status] += 1
        y['owners'][c.owner.name] += 1
        days_left = c.days_left
        if days_left is not None and days_left < 0:
            y['overdue'] += 1
        elif days_left is not None and days_left <= 7:
            y['due_week'] += 1
        y['containers'].append({
            'id': c.pk, 'code': c.code, 'description': c.description, 'status': c.status,
            'status_label': c.get_status_display(), 'owner': c.owner.name, 'vessel': c.vessel_voyage,
            'arrival': c.arrival_date.strftime('%d %b %Y') if c.arrival_date else '',
            'days_left': days_left, 'driver': c.driver, 'edit_url': reverse('cms_container_edit', args=[c.pk]),
        })
    out = []
    for y in yards.values():
        y['owners'] = y['owners'].most_common()
        out.append(y)
    return out


@login_required
@role_required(*CMS_ROLES)
def atlas(request):
    payload = {'yards': _atlas_payload()}
    return render(request, 'cms/atlas.html', {
        # Rendered inside <script>; escape '<' so user text cannot close the tag.
        'atlas_json': json.dumps(payload).replace('<', '\\u003c'),
        'focus': request.GET.get('yard', ''),
    })


@login_required
@role_required(*CMS_ROLES)
@require_POST
def yard_move(request, pk):
    """Save a yard pin dragged to its true position on the Atlas."""
    yard = get_object_or_404(Yard, pk=pk)
    try:
        lat, lng = float(request.POST['lat']), float(request.POST['lng'])
    except (KeyError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Bad position'}, status=400)
    # Keep pins on (or just off) Upolu.
    if not (-14.15 <= lat <= -13.70 and -172.15 <= lng <= -171.35):
        return JsonResponse({'ok': False, 'error': 'That is outside Upolu'}, status=400)
    yard.latitude, yard.longitude = round(lat, 6), round(lng, 6)
    yard.save(update_fields=['latitude', 'longitude'])
    return JsonResponse({'ok': True, 'lat': yard.latitude, 'lng': yard.longitude})
