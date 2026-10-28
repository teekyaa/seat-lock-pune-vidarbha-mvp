from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Every scheduled or immediate message is a row. The per-minute tick sends due rows."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.CASCADE)
    ride = models.ForeignKey("rides.Ride", null=True, blank=True, on_delete=models.CASCADE)
    send_at = models.DateTimeField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    url = models.CharField(max_length=200, blank=True)
    channels_sent = models.JSONField(default=list, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    dedupe_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-send_at"]
        indexes = [models.Index(fields=["status", "send_at"], name="notification_due_idx")]
