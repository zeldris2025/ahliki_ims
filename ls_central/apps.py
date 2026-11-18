from django.apps import AppConfig


class LsCentralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ls_central'
    verbose_name = 'LS Central'

    def ready(self):
        from . import auto_sync
        auto_sync.start()
