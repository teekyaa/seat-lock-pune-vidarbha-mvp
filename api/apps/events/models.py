"""Transactional outbox, consumer de-duplication and the metrics projection. See docs/EVENTS_KAFKA.md."""
import uuid

from django.db import models


class OutboxEvent(models.Model):
    """A domain event written in the same transaction as the change it describes.

    The relay publishes unpublished rows to Kafka and stamps published_at. Delivery is at-least-once,
    so consumers de-duplicate on event_id.
    """

    event_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    topic = models.CharField(max_length=80)
    key = models.CharField(max_length=64)  # partition key: ride code, user id or flag id
    type = models.CharField(max_length=60)
    payload = models.JSONField()  # the full envelope, exactly as published
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["published_at", "id"], name="outbox_unpublished"),
        ]

    def __str__(self):
        return f"{self.type} {self.key}"


class ProcessedEvent(models.Model):
    """One row per (consumer, event). The unique constraint turns a replayed message into a no-op."""

    consumer = models.CharField(max_length=60)
    event_id = models.UUIDField()
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["consumer", "event_id"], name="processed_event_once")]


class DailyMetric(models.Model):
    """Counts per IST day, built by the metrics consumer from the event stream."""

    day = models.DateField()  # IST calendar day of the event
    name = models.CharField(max_length=60)
    count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "name"], name="daily_metric_once")]
        ordering = ["-day", "name"]

    def __str__(self):
        return f"{self.day} {self.name}: {self.count}"
