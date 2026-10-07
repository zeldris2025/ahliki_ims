"""CSV import / export for the CMS container register.

Import is two-step: parse() validates every row and reports problems without
touching the database, then apply() writes the valid rows. A container code that
is already sitting in a yard is updated rather than duplicated.
"""
import csv
import io
import re
from datetime import datetime

from django.db import transaction

from .forms import normalise_container_code
from .models import CmsContainer, ContainerReturn, ShippingLine, Yard

COLUMNS = ['Container Code', 'Description', 'Yard', 'Status', 'Owned', 'Vessel Voyage', 'A/Date', 'Driver',
           'Note', 'Returned']

SAMPLE_ROWS = [
    ['SWLU1234567', "40' dry — rice and flour", 'HQ-ALW-VAI', 'FULL', 'SWIRE', 'Southern Lily 2441N',
     '03/10/2026', 'Sione T.', 'Seal 448812', 'No'],
    ['PFLU7654321', "20' reefer", 'MATAUTU', 'EMPTY', 'PFL', 'Capitaine Quiros 112', '28/09/2026', '', '', 'No'],
]

# Normalised header → field. Headers are lower-cased with everything but letters/digits removed.
HEADER_ALIASES = {
    'containercode': 'code', 'container': 'code', 'code': 'code', 'containerno': 'code',
    'containernumber': 'code',
    'description': 'description', 'desc': 'description',
    'yard': 'yard',
    'status': 'status',
    'owned': 'owner', 'owner': 'owner', 'ownedby': 'owner', 'shipping': 'owner', 'shippingline': 'owner',
    'vesselvoyage': 'vessel_voyage', 'vessel': 'vessel_voyage', 'voyage': 'vessel_voyage',
    'adate': 'arrival_date', 'arrivaldate': 'arrival_date', 'arrival': 'arrival_date', 'date': 'arrival_date',
    'driver': 'driver', 'deliveredby': 'driver', 'truckdriver': 'driver',
    'note': 'note', 'notes': 'note',
    'returned': 'returned',
}
REQUIRED = ['code', 'yard', 'status', 'owner']

# Samoa writes dates day-first.
DATE_FORMATS = ['%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y', '%d-%m-%y', '%d.%m.%Y', '%d %b %Y',
                '%d-%b-%y', '%d-%b-%Y', '%d %B %Y', '%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M:%S']
YES = {'yes', 'y', 'true', '1', 'returned'}
NO = {'no', 'n', 'false', '0', ''}

MAX_BYTES = 5 * 1024 * 1024


class ImportError_(Exception):
    """The file as a whole cannot be read (wrong type, no header, missing columns)."""


def _key(value):
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


def decode(raw_bytes):
    if len(raw_bytes) > MAX_BYTES:
        raise ImportError_('The file is larger than 5 MB — split it into smaller files.')
    for encoding in ('utf-8-sig', 'cp1252'):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportError_('Could not read the file — save it from Excel as "CSV UTF-8".')


def _parse_date(value):
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f'A/Date "{value}" is not a date — use DD/MM/YYYY')


def parse(text):
    """Return (rows, errors). rows: dicts ready for apply(); errors: (line, message)."""
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        raise ImportError_('The file is empty.')
    fields = [HEADER_ALIASES.get(_key(h)) for h in header]
    missing = [f for f in REQUIRED if f not in fields]
    if missing:
        names = {'code': 'Container Code', 'yard': 'Yard', 'status': 'Status', 'owner': 'Owned'}
        raise ImportError_('Missing column(s): ' + ', '.join(names[m] for m in missing) +
                           '. Download the template to see the expected headers.')

    yards = {_key(y.code): y for y in Yard.objects.all()}
    owners = {}
    for line in ShippingLine.objects.all():
        owners[_key(line.name)] = line
        # "BBE/MSA" also matches a cell that just says BBE or MSA.
        for part in re.split(r'[/,&]', line.name):
            owners.setdefault(_key(part), line)
    statuses = {_key(label): value for value, label in CmsContainer.STATUS_CHOICES}
    active = {c.code: c for c in CmsContainer.objects.filter(returned=False)}

    rows, errors, seen = [], [], {}
    for line_no, cells in enumerate(reader, start=2):
        if not any(c.strip() for c in cells):
            continue
        raw = {}
        for field, cell in zip(fields, cells):
            if field and field not in raw:
                raw[field] = cell.strip()
        problems = []

        code = normalise_container_code(raw.get('code', ''))
        if not code:
            problems.append('Container Code is blank')
        elif len(code) > 20:
            problems.append(f'Container Code "{code}" is longer than 20 characters')
        elif code in seen:
            problems.append(f'{code} is also on line {seen[code]}')

        yard = yards.get(_key(raw.get('yard')))
        if not yard:
            problems.append(f'Yard "{raw.get("yard", "")}" is not one of the yards' if raw.get('yard')
                            else 'Yard is blank')
        status = statuses.get(_key(raw.get('status')))
        if not status:
            problems.append(f'Status "{raw.get("status", "")}" must be FULL, STORAGE or EMPTY')
        owner = owners.get(_key(raw.get('owner')))
        if not owner:
            problems.append(f'Owned "{raw.get("owner", "")}" is not a shipping line — add it on the Shipping page first'
                            if raw.get('owner') else 'Owned is blank')
        try:
            arrival = _parse_date(raw.get('arrival_date', ''))
        except ValueError as e:
            arrival = None
            problems.append(str(e))
        returned_raw = raw.get('returned', '').strip().lower()
        if returned_raw not in YES | NO:
            problems.append(f'Returned "{raw.get("returned")}" must be Yes or No')

        if problems:
            errors.append((line_no, '; '.join(problems)))
            continue
        seen[code] = line_no
        existing = active.get(code)
        rows.append({
            'line': line_no,
            'code': code,
            'description': raw.get('description', '')[:255],
            'yard_id': yard.pk, 'yard': yard.code,
            'status': status,
            'owner_id': owner.pk, 'owner': owner.name,
            'vessel_voyage': raw.get('vessel_voyage', '')[:120],
            'arrival_date': arrival.isoformat() if arrival else '',
            'driver': raw.get('driver', '')[:120],
            'note': raw.get('note', ''),
            'returned': returned_raw in YES,
            'existing_id': existing.pk if existing else None,
        })
    return rows, errors


@transaction.atomic
def apply(rows, user):
    """Write parsed rows. Returns counts of created / updated / returned / skipped."""
    counts = {'created': 0, 'updated': 0, 'returned': 0, 'skipped': 0}
    for row in rows:
        values = {
            'description': row['description'], 'yard_id': row['yard_id'], 'status': row['status'],
            'owner_id': row['owner_id'], 'vessel_voyage': row['vessel_voyage'],
            'arrival_date': row['arrival_date'] or None, 'note': row['note'],
            'driver': row.get('driver', ''),
        }
        container = CmsContainer.objects.filter(code=row['code'], returned=False).first()
        if container:
            for k, v in values.items():
                setattr(container, k, v)
            container.save()
            counts['updated'] += 1
        elif row['returned'] and CmsContainer.objects.filter(
                code=row['code'], returned=True, arrival_date=values['arrival_date']).exists():
            counts['skipped'] += 1   # this visit is already in the returned history
            continue
        else:
            container = CmsContainer.objects.create(code=row['code'], created_by=user, **values)
            counts['created'] += 1
        if row['returned'] and not container.returned:
            mark_returned(container, None, 'CSV import', '', user)
            counts['returned'] += 1
    return counts


def mark_returned(container, returned_date, staff_name, driver, user):
    ContainerReturn.objects.create(
        container=container, description=container.description, yard=container.yard,
        status=container.status, returned_date=returned_date, staff_name=staff_name, driver=driver,
        recorded_by=user)
    container.returned = True
    container.save(update_fields=['returned', 'updated_at'])


def write_containers(response, containers):
    writer = csv.writer(response)
    writer.writerow(COLUMNS + ['Return Due', 'Days Left'])
    for c in containers:
        writer.writerow([
            c.code, c.description, c.yard.code, c.get_status_display().upper(), c.owner.name, c.vessel_voyage,
            c.arrival_date.strftime('%d/%m/%Y') if c.arrival_date else '', c.driver, c.note,
            'Yes' if c.returned else 'No',
            c.return_due.strftime('%d/%m/%Y') if c.return_due else '',
            '' if c.days_left is None else c.days_left,
        ])


def write_returns(response, returns):
    writer = csv.writer(response)
    writer.writerow(['Container', 'Description', 'Yard', 'Status', 'Location', 'Returned Date', 'Staff Name',
                     'Driver'])
    for r in returns:
        writer.writerow([
            r.container.code, r.description, r.yard.code if r.yard else '', r.get_status_display().upper(),
            r.location, r.returned_date.strftime('%d/%m/%Y') if r.returned_date else '', r.staff_name, r.driver,
        ])


def transfer(container, to_yard, transferred_date, driver, staff_name, note, user):
    """Move a container to another yard and keep a record of the move."""
    from .models import ContainerTransfer
    ContainerTransfer.objects.create(
        container=container, from_yard=container.yard, to_yard=to_yard, transferred_date=transferred_date,
        driver=driver, staff_name=staff_name, note=note, recorded_by=user)
    container.yard = to_yard
    container.save()   # save() so a transfer to the wharf adds the NOT YET RELEASED note
