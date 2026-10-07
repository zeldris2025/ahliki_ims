"""Background refresher for tracked shipments.

Started from InventoryConfig.ready() when the web server boots. Every few
minutes it re-syncs, with Terminal49, any B/L still on the water whose last
sync is older than settings.TRACKING_AUTO_REFRESH_HOURS (default 4). Set it
to 0 to turn the refresher off, e.g. when running `manage.py refresh_tracking`
from Windows Task Scheduler instead.
"""
import logging
import os
import sys
import threading

from django.conf import settings
from django.db import close_old_connections

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 10 * 60
_started = False
_lock = threading.Lock()


def refresh_hours():
    return float(getattr(settings, 'TRACKING_AUTO_REFRESH_HOURS', 4) or 0)


def should_start():
    """Only in a serving process — not for migrate, test, shell, etc. Under
    runserver's autoreloader, only in the child process that serves requests."""
    if refresh_hours() <= 0:
        return False
    argv = [os.path.basename(a) for a in sys.argv[:2]]
    if argv and argv[0] in ('manage.py', 'django-admin', 'django-admin.py'):
        if len(argv) < 2 or argv[1] != 'runserver':
            return False
        return os.environ.get('RUN_MAIN') == 'true' or '--noreload' in sys.argv
    return True  # WSGI/ASGI server (waitress, gunicorn, …)


def _run():
    from .terminal49 import refresh_stale
    stop = threading.Event()
    while not stop.wait(CHECK_EVERY_SECONDS):
        try:
            close_old_connections()
            synced, failed = refresh_stale(refresh_hours())
            if synced:
                logger.info('Auto-refreshed %s tracked shipment(s) with Terminal49 (%s failed).', synced, failed)
        except Exception:  # never let the refresher thread die
            logger.exception('Tracked shipment auto-refresh failed')
        finally:
            close_old_connections()


def start():
    global _started
    with _lock:
        if _started or not should_start():
            return
        _started = True
    threading.Thread(target=_run, name='tracking-auto-refresh', daemon=True).start()
    logger.info('Tracked shipment auto-refresh every %s hours started.', refresh_hours())
