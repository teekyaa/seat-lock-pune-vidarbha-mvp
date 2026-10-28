from django.contrib import admin

from .models import AuthToken, User, Vehicle


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

