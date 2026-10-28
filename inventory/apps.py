from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'

    def ready(self):
        from . import audit, auto_refresh
        audit.connect()
        auto_refresh.start()
