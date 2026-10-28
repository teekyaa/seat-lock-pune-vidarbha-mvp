from django.contrib import admin
from django.utils import timezone

from . import services
from .models import Block, ReliabilityEvent, Report, SeatWanted, Vouch


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["created_at", "reason", "reporter", "reported", "booking", "status"]
    list_filter = ["status", "reason"]
    search_fields = ["reporter__phone", "reported__phone", "booking__code"]
    readonly_fields = ["reporter", "reported", "booking", "reason", "details", "created_at", "resolved_at"]
    actions = ["mark_actioned", "dismiss"]

    @admin.action(description="Mark actioned")
    def mark_actioned(self, request, queryset):
        queryset.update(status=Report.Status.ACTIONED, resolved_at=timezone.now())

    @admin.action(description="Dismiss")
    def dismiss(self, request, queryset):
        queryset.update(status=Report.Status.DISMISSED, resolved_at=timezone.now())


@admin.register(ReliabilityEvent)
class ReliabilityEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "user", "kind", "ride", "booking", "reverses"]
    list_filter = ["kind"]
    search_fields = ["user__phone", "user__name", "booking__code"]
    actions = ["correct"]

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in ReliabilityEvent._meta.fields] if obj else []

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Record a correction that reverses these events")
    def correct(self, request, queryset):
        for event in queryset.filter(reversed_by__isnull=True).exclude(kind="correction"):
            services.record_event(event.user, ReliabilityEvent.Kind.CORRECTION, ride=event.ride, booking=event.booking,
                                  reverses=event, note=f"Reversed by {request.user}")
        services.refresh_reliability_view()


admin.site.register(Block)
admin.site.register(Vouch)
admin.site.register(SeatWanted)
