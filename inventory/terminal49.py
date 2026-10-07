"""Terminal49 container tracking + the voyage maths behind the Ah Liki Atlas.

Terminal49 (https://terminal49.com/docs) tracks a shipment once a tracking
request is registered for its bill of lading. On the free plan an API key may
*only* create tracking requests — reading the shipment back, vessel positions
and the route map all need a paid plan. Everything here degrades gracefully:
when Terminal49 refuses a read, the Atlas falls back to an estimated position
interpolated along the great-circle route between the port of loading and
Apia using the departure date and ETA.
"""
import json
import math
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .validators import looks_like_container

from .validators import looks_like_container

API_BASE = 'https://api.terminal49.com/v2'
TIMEOUT_SECONDS = 20
DEFAULT_SPEED_KNOTS = 15  # typical Pacific feeder service speed
DEMO_PREFIX = 'DEMO'     # B/L numbers starting with this are demos and never sent to Terminal49

# Apia wharf (Matautu), Samoa — every voyage on the Atlas ends here.
APIA = {'name': 'Apia, Samoa', 'locode': 'WSAPW', 'lat': -13.8270, 'lng': -171.7580}

# Ports that regularly ship to Samoa, keyed by UN/LOCODE: (name, lat, lng).
PORTS = {
    'WSAPW': ('Apia', -13.8270, -171.7580),
    'NZAKL': ('Auckland', -36.8420, 174.7860),
    'NZTRG': ('Tauranga', -37.6580, 176.1810),
    'NZLYT': ('Lyttelton', -43.6060, 172.7220),
    'NZNPE': ('Napier', -39.4750, 176.9180),
    'AUSYD': ('Sydney', -33.9680, 151.2180),
    'AUBNE': ('Brisbane', -27.3830, 153.1690),
    'AUMEL': ('Melbourne', -37.8300, 144.9200),
    'FJSUV': ('Suva', -18.1330, 178.4230),
    'FJLTK': ('Lautoka', -17.6050, 177.4400),
    'ASPPG': ('Pago Pago', -14.2760, -170.6880),
    'TOTBU': ("Nuku'alofa", -21.1340, -175.2000),
    'PFPPT': ('Papeete', -17.5350, -149.5690),
    'NCNOU': ('Noumea', -22.2650, 166.4380),
    'PGLAE': ('Lae', -6.7330, 146.9980),
    'USHNL': ('Honolulu', 21.3070, -157.8670),
    'USLAX': ('Los Angeles', 33.7400, -118.2600),
    'USLGB': ('Long Beach', 33.7540, -118.2160),
    'USOAK': ('Oakland', 37.7960, -122.2790),
    'USSEA': ('Seattle', 47.5800, -122.3500),
    'CNSHA': ('Shanghai', 31.3600, 121.6200),
    'CNNGB': ('Ningbo', 29.9330, 121.8500),
    'CNTAO': ('Qingdao', 36.0670, 120.3200),
    'CNXMN': ('Xiamen', 24.4600, 118.0700),
    'CNYTN': ('Yantian / Shenzhen', 22.5600, 114.2700),
    'CNNSA': ('Nansha / Guangzhou', 22.7500, 113.6000),
    'HKHKG': ('Hong Kong', 22.3000, 114.1700),
    'TWKHH': ('Kaohsiung', 22.6100, 120.2800),
    'KRPUS': ('Busan', 35.1000, 129.0400),
    'JPTYO': ('Tokyo', 35.6200, 139.7800),
    'JPYOK': ('Yokohama', 35.4500, 139.6600),
    'SGSIN': ('Singapore', 1.2650, 103.8200),
    'MYPKG': ('Port Klang', 3.0000, 101.3900),
    'THLCH': ('Laem Chabang', 13.0650, 100.8970),
    'VNSGN': ('Ho Chi Minh City', 10.7700, 106.7100),
    'IDJKT': ('Jakarta', -6.1000, 106.8800),
    'PHMNL': ('Manila', 14.5800, 120.9600),
    'INNSA': ('Nhava Sheva', 18.9500, 72.9500),
    'NLRTM': ('Rotterdam', 51.9500, 4.1400),
}


class Terminal49Error(Exception):
    def __init__(self, message, status=None, plan_limited=False):
        super().__init__(message)
        self.status = status
        self.plan_limited = plan_limited

    @property
    def rejected_number(self):
        """A 4xx about the request itself (bad/unknown number or carrier) — as
        opposed to a bad API key, a paid-plan limit, rate limiting or an outage."""
        return bool(self.status) and 400 <= self.status < 500 \
            and self.status not in (401, 403, 429) and not self.plan_limited


# ── HTTP client ───────────────────────────────────────────────────────────────

def api_key():
    return getattr(settings, 'TERMINAL49_API_KEY', '') or ''


def is_configured():
    return bool(api_key())


def _request(method, path, payload=None):
    if not is_configured():
        raise Terminal49Error('Terminal49 API key is not configured (TERMINAL49_API_KEY).')
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        API_BASE + path, data=body, method=method,
        headers={
            'Authorization': f'Token {api_key()}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = f'Terminal49 returned HTTP {e.code}'
        try:
            errors = json.loads(e.read()).get('errors') or []
            if errors:
                detail = '; '.join(err.get('detail') or err.get('title') or '' for err in errors).strip('; ')
        except (ValueError, AttributeError):
            pass
        raise Terminal49Error(detail, status=e.code,
                              plan_limited=(e.code in (401, 403) and 'paid plan' in detail.lower()))
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Terminal49Error(f'Could not reach Terminal49: {getattr(e, "reason", e)}')


def create_tracking_request(number, request_type='bill_of_lading', scac=''):
    """Register a B/L / booking / container with Terminal49. Works on the free plan."""
    attrs = {'request_type': request_type, 'request_number': number}
    if scac:
        attrs['scac'] = scac
    else:
        attrs['auto_detect_vocc_scac'] = True
    data = _request('POST', '/tracking_requests',
                    {'data': {'type': 'tracking_request', 'attributes': attrs}}).get('data') or {}
    a = data.get('attributes') or {}
    tracked = ((data.get('relationships') or {}).get('tracked_object') or {}).get('data') or {}
    return {
        'id': data.get('id', ''),
        'status': a.get('status') or 'pending',
        'failed_reason': a.get('failed_reason') or '',
        'scac': a.get('scac') or scac,
        'shipment_id': tracked.get('id', '') if tracked.get('type') == 'shipment' else '',
    }


def get_tracking_request(request_id):
    data = _request('GET', f'/tracking_requests/{request_id}').get('data') or {}
    a = data.get('attributes') or {}
    tracked = ((data.get('relationships') or {}).get('tracked_object') or {}).get('data') or {}
    return {
        'status': a.get('status') or '',
        'failed_reason': a.get('failed_reason') or '',
        'shipment_id': tracked.get('id', '') if tracked.get('type') == 'shipment' else '',
    }


def get_shipment(shipment_id):
    resp = _request('GET', f'/shipments/{shipment_id}?include=containers')
    a = (resp.get('data') or {}).get('attributes') or {}
    containers = [inc for inc in resp.get('included') or [] if inc.get('type') == 'container']
    return {
        'shipping_line': a.get('shipping_line_name') or a.get('shipping_line_short_name') or '',
        'scac': a.get('shipping_line_scac') or '',
        'vessel_name': a.get('pod_vessel_name') or '',
        'voyage_number': a.get('pod_voyage_number') or '',
        'origin_port': a.get('port_of_lading_name') or a.get('port_of_lading_locode') or '',
        'destination_port': a.get('port_of_discharge_name') or '',
        'departed_at': _dt(a.get('pol_atd_at') or a.get('pol_etd_at')),
        'eta_at': _dt(a.get('pod_eta_at')),
        'arrived_at': _dt(a.get('pod_ata_at')),
        'container_numbers': [(c.get('attributes') or {}).get('number', '') for c in containers],
        'container_ids': [c.get('id') for c in containers if c.get('id')],
    }


def get_container_map(container_id):
    """Route GeoJSON with the vessel's current position (paid feature)."""
    return _request('GET', f'/containers/{container_id}/map_geojson')


def _dt(value):
    return parse_datetime(value) if value else None


# ── Sync a ShipmentTracking with Terminal49 ───────────────────────────────────

PLAN_LIMITED_MESSAGE = ('Registered with Terminal49. Live voyage data needs a paid Terminal49 plan, '
                        'so the Atlas is estimating the ship position from the ETD/ETA.')


def sync_tracking(tracking):
    """Push/pull one tracked shipment. Never raises — the outcome is stored on the
    record (t49_status / last_sync_message) and returned as (ok, message)."""
    now = timezone.now()
    tracking.last_synced_at = now
    if tracking.is_demo:
        # Made-up demo numbers would only create failing requests on the Terminal49 account.
        tracking.last_sync_message = 'Demo shipment — not sent to Terminal49; position is estimated.'
        tracking.save()
        return True, tracking.last_sync_message
    try:
        if not tracking.t49_request_id:
            # Terminal49 refuses a container number sent as a B/L, so never trust a wrong pick.
            if tracking.request_type != 'container' and looks_like_container(tracking.request_number):
                tracking.request_type = 'container'
            result = create_tracking_request(tracking.request_number, tracking.request_type, tracking.scac)
            tracking.t49_request_id = result['id']
            tracking.t49_status = result['status']
            tracking.t49_failed_reason = result['failed_reason']
            tracking.scac = tracking.scac or (result['scac'] or '')
            tracking.t49_shipment_id = result['shipment_id'] or tracking.t49_shipment_id
        else:
            result = get_tracking_request(tracking.t49_request_id)
            tracking.t49_status = result['status'] or tracking.t49_status
            tracking.t49_failed_reason = result['failed_reason']
            tracking.t49_shipment_id = result['shipment_id'] or tracking.t49_shipment_id

        if tracking.t49_shipment_id:
            _apply_shipment(tracking, get_shipment(tracking.t49_shipment_id))

        if tracking.t49_status == 'failed':
            message = f'Terminal49 could not track this number: {tracking.t49_failed_reason or "unknown reason"}'
        else:
            message = 'Synced with Terminal49.'
        tracking.last_sync_message = message[:255]
        tracking.save()
        return tracking.t49_status != 'failed', message

    except Terminal49Error as e:
        if e.plan_limited:
            message = PLAN_LIMITED_MESSAGE if tracking.t49_request_id else str(e)
            ok = bool(tracking.t49_request_id)
        elif not tracking.t49_request_id:
            # Duplicate numbers come back as 422 — Terminal49 is already tracking it.
            ok = e.status == 422 and 'already' in str(e).lower()
            if ok:
                tracking.t49_status = 'created'
                message = 'Terminal49 is already tracking this number.'
            elif e.rejected_number:
                # Terminal49 looked at the number and refused it — it is not a real shipment.
                tracking.t49_status = 'failed'
                tracking.t49_failed_reason = str(e)[:255]
                message = f'Terminal49 rejected this number: {e}'
            else:
                message = f'Could not register with Terminal49: {e}'
        else:
            ok, message = False, f'Terminal49 sync failed: {e}'
        tracking.last_sync_message = message[:255]
        tracking.save()
        return ok, message


def _apply_shipment(tracking, s):
    for field in ('shipping_line', 'vessel_name', 'voyage_number', 'origin_port',
                  'destination_port', 'departed_at', 'eta_at', 'arrived_at'):
        if s.get(field):
            setattr(tracking, field, s[field])
    if s.get('scac') and not tracking.scac:
        tracking.scac = s['scac']
    known = tracking.container_number_list
    extra = [n for n in s.get('container_numbers', []) if n and n.upper() not in known]
    if extra:
        tracking.container_numbers = '\n'.join(known + extra)

    for container_id in s.get('container_ids', [])[:1]:
        geo = get_container_map(container_id)
        tracking.route_geojson = json.dumps(geo)
        for f in geo.get('features') or []:
            props = f.get('properties') or {}
            if props.get('feature_type') == 'current_vessel':
                lng, lat = f['geometry']['coordinates'][:2]
                tracking.latitude, tracking.longitude = lat, lng
                tracking.heading = props.get('vessel_location_heading')
                tracking.speed_knots = props.get('vessel_location_speed')
                tracking.position_at = _dt(props.get('vessel_location_timestamp')) or timezone.now()


# ── Ports + voyage estimation for the Atlas ──────────────────────────────────

def resolve_port(text):
    """Find a port's coordinates from a LOCODE or a (partial) name."""
    if not text:
        return None
    t = text.strip().upper().replace(' ', '')
    if t in PORTS:
        name, lat, lng = PORTS[t]
        return {'name': name, 'locode': t, 'lat': lat, 'lng': lng}
    needle = text.strip().lower().split(',')[0].strip()
    for code, (name, lat, lng) in PORTS.items():
        names = [n.strip().lower() for n in name.split('/')]
        if any(needle == n or (len(needle) >= 4 and (needle in n or n in needle)) for n in names):
            return {'name': name, 'locode': code, 'lat': lat, 'lng': lng}
    return None


def port_choices():
    return [f'{name} ({code})' for code, (name, _, _) in sorted(PORTS.items(), key=lambda p: p[1][0])
            if code != 'WSAPW']


def _to_vec(lat, lng):
    la, lo = math.radians(lat), math.radians(lng)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def great_circle(a, b, steps=96):
    """Points along the great circle from a to b as [lat, lng], with longitudes
    unwrapped so the line never jumps across the antimeridian on the map."""
    va, vb = _to_vec(a['lat'], a['lng']), _to_vec(b['lat'], b['lng'])
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(va, vb))))
    omega = math.acos(dot)
    points = []
    for i in range(steps + 1):
        f = i / steps
        if omega < 1e-9:
            v = va
        else:
            s1 = math.sin((1 - f) * omega) / math.sin(omega)
            s2 = math.sin(f * omega) / math.sin(omega)
            v = tuple(s1 * x + s2 * y for x, y in zip(va, vb))
        lat = math.degrees(math.atan2(v[2], math.hypot(v[0], v[1])))
        lng = math.degrees(math.atan2(v[1], v[0]))
        if points:
            prev = points[-1][1]
            while lng - prev > 180:
                lng -= 360
            while lng - prev < -180:
                lng += 360
        points.append([round(lat, 4), round(lng, 4)])
    # Keep the Pacific in view: shift so the route sits around Samoa (lng ~ -171 → 189).
    if points and points[-1][1] < 0:
        points = [[lat, lng + 360] for lat, lng in points]
    return points, omega * 3440.065  # nautical miles


def voyage(tracking):
    """Everything the Atlas needs to draw one shipment, or None if we cannot
    place it (no known port of loading and no live position)."""
    origin = resolve_port(tracking.origin_port)
    live = tracking.latitude is not None and tracking.longitude is not None
    if not origin and not live:
        return None

    now = timezone.now()
    route, distance_nm = ([], 0)
    if origin:
        route, distance_nm = great_circle(origin, APIA)

    transit = timedelta(hours=distance_nm / DEFAULT_SPEED_KNOTS) if distance_nm else timedelta(days=7)
    departed = tracking.departed_at or (tracking.eta_at - transit if tracking.eta_at else None)
    eta = tracking.eta_at or (departed + transit if departed else None)
    if departed is None:
        # Nothing to time the voyage against — show it as just leaving port.
        departed, eta = now, now + transit

    arrived = bool(tracking.arrived_at) or tracking.lodged_count > 0
    if arrived:
        progress = 1.0
    else:
        span = (eta - departed).total_seconds()
        progress = 0.0 if span <= 0 else max(0.0, min(1.0, (now - departed).total_seconds() / span))

    if live and not arrived:
        lng = tracking.longitude
        if route:
            ref = route[-1][1]
            while lng - ref > 180:
                lng -= 360
            while lng - ref < -180:
                lng += 360
        elif lng < 0:
            lng += 360
        position = [tracking.latitude, lng]
        source = 'live'
    elif route:
        idx = progress * (len(route) - 1)
        i = min(int(idx), len(route) - 2)
        f = idx - i
        position = [route[i][0] + (route[i + 1][0] - route[i][0]) * f,
                    route[i][1] + (route[i + 1][1] - route[i][1]) * f]
        source = 'arrived' if arrived else 'estimated'
    else:
        position = [APIA['lat'], APIA['lng'] + 360]
        source = 'arrived'

    days_left = (eta - now).total_seconds() / 86400 if eta else None
    return {
        'id': tracking.pk,
        'number': tracking.request_number,
        'vessel': ' '.join(filter(None, [tracking.vessel_name, tracking.voyage_number])) or 'Vessel TBC',
        'line': tracking.shipping_line or tracking.scac,
        'supplier': tracking.supplier.name if tracking.supplier else '',
        'origin': origin['name'] if origin else (tracking.origin_port or 'Unknown'),
        'containers': tracking.container_number_list,
        'route': route,
        'position': [round(position[0], 4), round(position[1], 4)],
        'heading': tracking.heading,
        'speed': tracking.speed_knots,
        'source': source,
        'progress': round(progress, 4),
        'departed': departed.isoformat() if departed else None,
        'eta': eta.isoformat() if eta else None,
        'eta_label': timezone.localtime(eta).strftime('%a %d %b %Y') if eta else 'TBC',
        'days_left': round(days_left, 1) if days_left is not None else None,
        'distance_nm': round(distance_nm),
        't49_status': tracking.get_t49_status_display(),
        'route_geojson': json.loads(tracking.route_geojson) if tracking.route_geojson else None,
    }


# ── Scheduled refresh ─────────────────────────────────────────────────────────

def refresh_stale(hours):
    """Re-sync every shipment still on the water whose last sync is older than
    `hours`. Each record is claimed with a conditional UPDATE first, so several
    server processes running the refresher never sync the same B/L twice."""
    from django.db.models import Q
    from .models import ShipmentTracking

    cutoff = timezone.now() - timedelta(hours=hours)
    stale = ShipmentTracking.objects.filter(arrived_at__isnull=True, containers__isnull=True) \
        .exclude(t49_status__in=['failed', 'tracking_stopped']) \
        .exclude(request_number__startswith=DEMO_PREFIX) \
        .filter(Q(last_synced_at__isnull=True) | Q(last_synced_at__lt=cutoff)).distinct()
    synced = failed = 0
    for tracking in stale:
        claimed = ShipmentTracking.objects.filter(pk=tracking.pk, last_synced_at=tracking.last_synced_at) \
            .update(last_synced_at=timezone.now())
        if not claimed:
            continue
        ok, _ = sync_tracking(tracking)
        synced += 1
        failed += 0 if ok else 1
    return synced, failed
