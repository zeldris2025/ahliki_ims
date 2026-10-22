# gunicorn reads this file automatically from the working directory (/app in the container).
# Azure tells the container which port to listen on through PORT / WEBSITES_PORT; 8000 otherwise.
import os

bind = f"0.0.0.0:{os.environ.get('PORT') or os.environ.get('WEBSITES_PORT') or 8000}"
workers = int(os.environ.get('WEB_CONCURRENCY', 3))
timeout = 120
accesslog = '-'
errorlog = '-'
forwarded_allow_ips = '*'   # Azure's front end sits in front of the container
