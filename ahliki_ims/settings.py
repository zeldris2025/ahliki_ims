import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_list(name, default=''):
    return [v.strip() for v in os.environ.get(name, default).split(',') if v.strip()]


# Docker sets these from .env (see docker-compose.yml); running locally without them keeps the old defaults.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-ahliki-ims-change-in-production-2026')
DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() in ('1', 'true', 'yes')
ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', '*')
# Full origins the site is opened from, e.g. http://10.10.8.49:8080 — needed for logins/forms behind a port map.
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS')

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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': Path(os.environ.get('SQLITE_PATH', BASE_DIR / 'db.sqlite3')),
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
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

# Terminal49 container tracking (Track Containers + Ah Liki Atlas).
# Set the key via the TERMINAL49_API_KEY environment variable or in
# ahliki_ims/local_settings.py (git-ignored) — never commit it.
TERMINAL49_API_KEY = os.environ.get('TERMINAL49_API_KEY', '')
# Re-sync tracked B/Ls still on the water this often (hours); 0 turns the background refresher off.
TRACKING_AUTO_REFRESH_HOURS = 4

try:
    from .local_settings import *  # noqa: F401,F403
except ImportError:
    pass
