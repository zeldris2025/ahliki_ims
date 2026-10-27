from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'

    def ready(self):
        from . import auto_refresh, scheduler
        auto_refresh.start()
        scheduler.start()
