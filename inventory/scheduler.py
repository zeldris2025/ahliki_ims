"""Daily jobs run inside the web app, so nothing extra has to be set up on Azure.

Started from InventoryConfig.ready(). Every few minutes each serving process checks whether a job's
time of day (Apia time) has passed; the first process to record today's ScheduledRun row does the work,
so it runs once a day however many gunicorn workers or Azure instances there are. If the app was down
at that time, the job runs as soon as it comes back up the same day.

Needs the app to stay awake: on Azure App Service turn on Configuration → General settings → Always On.
"""
import logging
import threading
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, close_old_connections, transaction
from django.utils import timezone

from .auto_refresh import is_serving_process

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 5 * 60
_started = False
_lock = threading.Lock()


def _jobs():
    """(name, 'HH:MM' or '', function returning a short result line)."""
    from .container_report import send_report
    return [('container_report', settings.CONTAINER_REPORT_TIME, send_report)]


def is_due(at, now=None):
    if not at:
        return False
    now = now or timezone.localtime()
    return now.time() >= datetime.strptime(at, '%H:%M').time()


def run_once_today(job, func):
    """Run func unless today's run of this job is already claimed. Returns its result, or None if skipped.
    A failed run gives up its claim so the next check tries again."""
    from .models import ScheduledRun
    today = timezone.localdate()
    if ScheduledRun.objects.filter(job=job, run_date=today).exists():
        return None
    try:
        with transaction.atomic():
            run = ScheduledRun.objects.create(job=job, run_date=today)
    except IntegrityError:
        return None   # another worker got there first
    try:
        result = func()
    except Exception:
        run.delete()
        raise
    run.finished_at = timezone.now()
    run.result = str(result)[:255]
    run.save(update_fields=['finished_at', 'result'])
    return result


def check():
    for job, at, func in _jobs():
        if not is_due(at):
            continue
        try:
            result = run_once_today(job, func)
            if result is not None:
                logger.info('Scheduled job %s: %s', job, result)
        except Exception:
            logger.exception('Scheduled job %s failed; will retry in %s minutes', job, CHECK_EVERY_SECONDS // 60)


def _run():
    stop = threading.Event()
    while True:
        try:
            close_old_connections()
            check()
        except Exception:   # never let the scheduler thread die
            logger.exception('Scheduler check failed')
        finally:
            close_old_connections()
        if stop.wait(CHECK_EVERY_SECONDS):
            return


def start():
    global _started
    with _lock:
        if _started or not is_serving_process() or not any(at for _, at, _ in _jobs()):
            return
        _started = True
    threading.Thread(target=_run, name='daily-scheduler', daemon=True).start()
    logger.info('Daily scheduler started: %s', ', '.join(f'{job} at {at}' for job, at, _ in _jobs() if at))
