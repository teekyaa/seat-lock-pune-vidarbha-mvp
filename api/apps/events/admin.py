from django.contrib import admin

from .models import DailyMetric, OutboxEvent


@admin.register(DailyMetric)
class DailyMetricAdmin(admin.ModelAdmin):
    """Built by the metrics consumer from Kafka. Read-only: fix the source event, never the count."""

    list_display = ["day", "name", "count", "updated_at"]
    list_filter = ["name"]
    date_hierarchy = "day"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OutboxEvent)
class OutboxEventAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "key", "topic", "occurred_at", "published_at", "attempts", "last_error"]
    list_filter = ["topic", "type"]
    search_fields = ["key", "event_id"]
    readonly_fields = [f.name for f in OutboxEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
