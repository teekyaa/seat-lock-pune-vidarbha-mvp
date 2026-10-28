from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["send_at", "user", "kind", "status", "attempts", "channels_sent"]
    list_filter = ["status", "kind"]
    search_fields = ["user__phone", "booking__code"]
