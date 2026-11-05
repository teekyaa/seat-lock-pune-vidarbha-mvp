from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import AuthToken, OTPAbuseFlag, User, Vehicle


class BlockedNowFilter(admin.SimpleListFilter):
    title = "blocked now"
    parameter_name = "blocked"

    def lookups(self, request, model_admin):
        return [("yes", "Blocked now"), ("no", "Not blocked")]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "yes":
            return queryset.filter(blocked_until__gt=now)
        if self.value() == "no":
            return queryset.exclude(blocked_until__gt=now)
        return queryset


@admin.register(OTPAbuseFlag)
class OTPAbuseFlagAdmin(admin.ModelAdmin):
    """Numbers and IPs that kept hitting sign-in code limits. Blocks lift on their own at blocked_until."""

    list_display = ["kind", "value", "reason", "hits", "total_hits", "times_blocked", "blocked_until", "last_seen",
                    "reviewed_at"]
    list_filter = [BlockedNowFilter, "kind", "reason"]
    search_fields = ["value"]
    ordering = ["-last_seen"]
    readonly_fields = ["kind", "value", "reason", "hits", "total_hits", "times_blocked", "first_seen", "last_seen",
                       "blocked_until", "reviewed_at"]
    fields = readonly_fields + ["note"]
    actions = ["unblock", "mark_reviewed", "block_for_a_week"]

    def has_add_permission(self, request):
        return False  # rows come only from real limit hits

    @admin.action(description="Unblock now and mark reviewed")
    def unblock(self, request, queryset):
        queryset.update(blocked_until=None, hits=0, reviewed_at=timezone.now())

    @admin.action(description="Mark reviewed (keep any block)")
    def mark_reviewed(self, request, queryset):
        queryset.update(reviewed_at=timezone.now())

    @admin.action(description="Block code requests for 7 days")
    def block_for_a_week(self, request, queryset):
        now = timezone.now()
        queryset.update(blocked_until=now + timedelta(days=7), reviewed_at=now)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["phone", "name", "hometown", "gender", "women_only_eligible", "id_verification_result",
                    "is_active", "date_joined"]
    list_filter = ["women_only_eligible", "id_verification_result", "is_active", "is_staff", "gender"]
    search_fields = ["phone", "name", "email"]
    readonly_fields = ["id", "date_joined", "last_login", "terms_accepted_at"]
    exclude = ["password", "groups", "user_permissions"]
    actions = ["verify_women_only", "suspend"]

    @admin.action(description="Mark as verified for women-only rides")
    def verify_women_only(self, request, queryset):
        queryset.update(women_only_eligible=True)

    @admin.action(description="Suspend (blocks sign-in)")
    def suspend(self, request, queryset):
        queryset.update(is_active=False)
        AuthToken.objects.filter(user__in=queryset).delete()


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ["owner", "make_model", "colour", "registration", "passenger_seats"]
    search_fields = ["registration", "owner__phone", "owner__name"]

