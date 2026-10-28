from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'

    def ready(self):
        from . import audit, auto_refresh, scheduler
        audit.connect()
        auto_refresh.start()
        scheduler.start()
