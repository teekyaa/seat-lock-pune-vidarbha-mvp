from django.contrib import admin

from .models import AuditLog, CityPair, PolicyVersion, Season


@admin.register(CityPair)
class CityPairAdmin(admin.ModelAdmin):
    list_display = ["origin", "destination", "distance_km", "tolls_inr", "typical_duration_hours", "active", "updated_at"]
    list_editable = ["distance_km", "tolls_inr", "active"]


@admin.register(PolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    list_display = ["label", "effective_from", "advance_percent", "fuel_cost_per_km", "fare_cap_percent"]

    def get_readonly_fields(self, request, obj=None):
        # A version that bookings depend on is frozen; publish a new one instead.
        if obj and obj.bookings.exists():
            return [f.name for f in obj._meta.fields]
        return []


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["name", "starts_at", "ends_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "object_type", "object_id"]
    list_filter = ["action", "object_type"]
    search_fields = ["object_id", "actor__phone"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
