from django.contrib import admin, messages

from . import services
from .models import Booking, NoShowCase, Payment, WaitlistEntry


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = ["kind", "amount_inr", "status", "utr", "due_at", "dispute_at", "claimed_at", "confirmed_at",
                       "overdue_flagged_at"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["code", "ride", "passenger", "status", "advance_inr", "refund_outcome", "at_risk", "created_at"]
    list_filter = ["status", "refund_outcome", "at_risk"]
    search_fields = ["code", "passenger__phone", "passenger__name", "ride__code"]
    inlines = [PaymentInline]
    # Status changes go through the booking services, never by hand.
    readonly_fields = [f.name for f in Booking._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(NoShowCase)
class NoShowCaseAdmin(admin.ModelAdmin):
    list_display = ["booking", "status", "marked_at", "dispute_until", "disputed_at"]
    list_filter = ["status"]
    readonly_fields = ["booking", "marked_at", "dispute_until", "status", "disputed_at", "passenger_statement",
                       "resolved_at"]
    actions = ["uphold", "overturn"]

    @admin.action(description="Uphold: the no-show stands")
    def uphold(self, request, queryset):
        for case in queryset.filter(status__in=["pending", "disputed"]):
            services.finalise_no_show(case, upheld=True, staff=request.user, note=case.resolution_note)
        messages.success(request, "Upheld.")

    @admin.action(description="Overturn: the passenger was there")
    def overturn(self, request, queryset):
        for case in queryset.filter(status__in=["pending", "disputed"]):
            services.finalise_no_show(case, upheld=False, staff=request.user, note=case.resolution_note)
        messages.success(request, "Overturned.")


@admin.register(WaitlistEntry)
class WaitlistAdmin(admin.ModelAdmin):
    list_display = ["ride", "passenger", "status", "offer_expires_at", "created_at"]
    list_filter = ["status"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["booking", "kind", "amount_inr", "status", "due_at", "overdue_flagged_at"]
    list_filter = ["kind", "status"]
    readonly_fields = [f.name for f in Payment._meta.fields]

    def has_add_permission(self, request):
        return False
