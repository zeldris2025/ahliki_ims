"""Checks LS Central for new invoices every LS_CENTRAL_SYNC_MINUTES while the website runs.

Started from LsCentralConfig.ready(). Does nothing until the keys are filled in. With several
gunicorn workers each runs this loop, but a worker skips its turn when another one synced
recently, and an invoice can only be imported once.
"""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()


def interval_minutes():
    return float(getattr(settings, 'LS_CENTRAL_SYNC_MINUTES', 0) or 0)


def _run():
    from .client import is_configured
    from .models import LsCentralSync
    from .sync import sync_invoices
    minutes = interval_minutes()
    stop = threading.Event()
    while not stop.wait(minutes * 60):
        try:
            close_old_connections()
            if not is_configured():
                continue
            recent = timezone.now() - timedelta(minutes=minutes * 0.8)
            if LsCentralSync.objects.filter(started_at__gte=recent).exists():
                continue
            run = sync_invoices()
            if run.imported or not run.ok:
                logger.info('LS Central auto-sync: %s', run.message)
        except Exception:   # never let the thread die
            logger.exception('LS Central auto-sync failed')
        finally:
            close_old_connections()


def start():
    global _started
    from inventory.auto_refresh import is_serving_process
    with _lock:
        if _started or interval_minutes() <= 0 or not is_serving_process():
            return
        _started = True
    threading.Thread(target=_run, name='ls-central-auto-sync', daemon=True).start()
    logger.info('LS Central auto-sync every %s minutes started.', interval_minutes())
