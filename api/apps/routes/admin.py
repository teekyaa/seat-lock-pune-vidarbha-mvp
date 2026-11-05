from django.contrib import admin, messages
from django.utils import timezone

from . import mappls
from .models import Leg, Place, Route, RouteStop
from .services import segment


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "region", "aliases", "lat", "lng", "mappls_eloc"]
    list_filter = ["region"]
    search_fields = ["name", "aliases"]


@admin.register(Leg)
class LegAdmin(admin.ModelAdmin):
    list_display = ["__str__", "distance_km", "tolls_inr", "typical_minutes", "source", "verified_at", "verified_by"]
    list_filter = ["source", ("verified_at", admin.EmptyFieldListFilter)]
    search_fields = ["from_place__name", "to_place__name"]
    readonly_fields = ["verified_at", "verified_by", "updated_at"]
    actions = ["measure_with_mappls", "mark_verified"]

    def save_model(self, request, obj, form, change):
        # Any edit to the figures needs a fresh check by a person.
        if change and {"distance_km", "tolls_inr", "typical_minutes"} & set(form.changed_data):
            obj.verified_at = None
            obj.verified_by = None
            if obj.source == Leg.Source.MAPPLS and "distance_km" in form.changed_data:
                obj.source = Leg.Source.MANUAL
        super().save_model(request, obj, form, change)

    @admin.action(description="Measure distance and time with Mappls (needs checking afterwards)")
    def measure_with_mappls(self, request, queryset):
        done = 0
        for leg in queryset.select_related("from_place", "to_place"):
            try:
                mappls.measure_leg(leg)
                done += 1
            except mappls.MapplsUnavailable as exc:
                messages.error(request, f"{leg}: {exc}")
                break
        if done:
            messages.success(request, f"Measured {done} leg(s). Check each one, then mark it verified.")

    @admin.action(description="Mark verified (distance and tolls checked by me)")
    def mark_verified(self, request, queryset):
        missing = [str(leg) for leg in queryset if not leg.measured]
        if missing:
            messages.error(request, "Add distance and tolls first: " + ", ".join(missing))
            return
        count = queryset.update(verified_at=timezone.now(), verified_by=request.user)
        messages.success(request, f"Verified {count} leg(s).")


class RouteStopInline(admin.TabularInline):
    model = RouteStop
    extra = 1
    ordering = ["position"]


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "active", "status"]
    list_filter = ["active"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [RouteStopInline]

    @admin.display(description="Status")
    def status(self, route):
        stops = list(route.stops.select_related("place").order_by("position"))
        if len(stops) < 2:
            return "Add at least two stops"
        seg = segment(route, stops[0].place, stops[-1].place, require_ready=False)
        if seg.missing:
            return "Missing legs: " + ", ".join(f"{a} to {b}" for a, b in seg.missing)
        pending = [str(leg) for leg in seg.legs if not leg.ready()]
        return f"{seg.distance_km} km, ready" if not pending else "Needs checking: " + ", ".join(pending)
