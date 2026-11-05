from django.apps import AppConfig


class AdminDashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.admin_dashboard"
    verbose_name = "Separate administration"

    def ready(self):
        from . import schema_auth  # noqa: F401
