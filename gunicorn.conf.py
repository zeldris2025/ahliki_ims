# gunicorn reads this file automatically from the working directory (/app in the container).
# Azure tells the container which port to listen on through PORT / WEBSITES_PORT; 8000 otherwise.
import os

bind = f"0.0.0.0:{os.environ.get('PORT') or os.environ.get('WEBSITES_PORT') or 8000}"
workers = int(os.environ.get('WEB_CONCURRENCY', 3))
timeout = 120
accesslog = '-'
errorlog = '-'
forwarded_allow_ips = '*'   # Azure's front end sits in front of the container

# LIVE_RELOAD=1 (docker-compose.dev.yml): restart workers when code or a template changes.
# Polling, because file-change events don't cross a Windows bind mount.
if os.environ.get('LIVE_RELOAD', '').lower() in ('1', 'true', 'yes'):
    from pathlib import Path
    reload = True
    reload_engine = 'poll'
    reload_extra_files = [str(p) for p in Path(__file__).resolve().parent.glob('templates/**/*.html')]
