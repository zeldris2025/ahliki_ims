import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


def env_bool(name, default):
    return os.environ.get(name, str(default)).lower() in ('1', 'true', 'yes')


# Azure gives the app its own address and sets it in the environment: App Service sets WEBSITE_HOSTNAME
# (e.g. ahliki-ims.azurewebsites.net), Container Apps sets the app name + environment DNS suffix.
# Those are trusted automatically, so nothing here names a domain. A custom domain added later just
# goes into DJANGO_ALLOWED_HOSTS (and DJANGO_CSRF_TRUSTED_ORIGINS) in the Azure settings.
AZURE_HOSTS = [h for h in (
    os.environ.get('WEBSITE_HOSTNAME', ''),
    '.'.join(filter(None, (os.environ.get('CONTAINER_APP_NAME'), os.environ.get('CONTAINER_APP_ENV_DNS_SUFFIX'))))
    if os.environ.get('CONTAINER_APP_ENV_DNS_SUFFIX') else '',
) if h]
ON_AZURE = bool(AZURE_HOSTS)

# Docker sets these from .env (see docker-compose.yml); running locally without them keeps the old defaults.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if ON_AZURE:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY in the Azure app settings.')
    SECRET_KEY = 'django-insecure-ahliki-ims-change-in-production-2026'
DEBUG = env_bool('DJANGO_DEBUG', not ON_AZURE)
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS') + AZURE_HOSTS
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ['*']
# Full origins the site is opened from, e.g. http://10.10.8.49:8080 — needed for logins/forms behind a port map.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS') + [f'https://{h}' for h in AZURE_HOSTS]

# HTTPS. Azure ends TLS in front of the app and passes the original scheme in X-Forwarded-Proto.
# On by default on Azure; the office Docker install stays on plain http unless DJANGO_HTTPS=true.
if env_bool('DJANGO_HTTPS', ON_AZURE):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', 3600))
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'inventory',
]

MIDDLEWARE = [
    # First, so Azure's health probes get a 200 before host checks or the HTTPS redirect.
    'ahliki_ims.health.HealthCheckMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ahliki_ims.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'inventory.context_processors.alerts_count',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ahliki_ims.wsgi.application'

# DATABASE_URL (e.g. Azure Database for PostgreSQL) when set, otherwise the SQLite file.
if os.environ.get('DATABASE_URL'):
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(os.environ['DATABASE_URL'], conn_max_age=600,
                                                  conn_health_checks=True)}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': Path(os.environ.get('SQLITE_PATH', BASE_DIR / 'db.sqlite3')),
            'OPTIONS': {'timeout': 20},
        }
    }

AUTH_PASSWORD_VALIDATORS = []
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Pacific/Apia'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))

# WhiteNoise serves /static/ under gunicorn (always installed in Docker). Optional for runserver.
try:
    import whitenoise  # noqa: F401
except ImportError:
    pass
else:
    MIDDLEWARE.insert(MIDDLEWARE.index('django.middleware.security.SecurityMiddleware') + 1,
                      'whitenoise.middleware.WhiteNoiseMiddleware')
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
    }
    # LIVE_RELOAD (docker-compose.dev.yml): serve static/ as it is on disk, so CSS/JS edits show on refresh.
    WHITENOISE_USE_FINDERS = WHITENOISE_AUTOREFRESH = env_bool('LIVE_RELOAD', DEBUG)
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Terminal49 container tracking (Track Containers + Ah Liki Atlas).
# Set the key via the TERMINAL49_API_KEY environment variable or in
# ahliki_ims/local_settings.py (git-ignored) — never commit it.
TERMINAL49_API_KEY = os.environ.get('TERMINAL49_API_KEY', '')
# Re-sync tracked B/Ls still on the water this often (hours); 0 turns the background refresher off.
TRACKING_AUTO_REFRESH_HOURS = float(os.environ.get('TRACKING_AUTO_REFRESH_HOURS', 4))

# Errors and warnings go to the console, which is what Azure's log stream shows.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO')},
}

try:
    from .local_settings import *  # noqa: F401,F403
except ImportError:
    pass
