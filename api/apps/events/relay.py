"""Outbox relay: publish unpublished outbox rows to Kafka, then mark them published.

At-least-once: a crash after Kafka acks but before the UPDATE re-sends those rows, and consumers
de-duplicate by event_id. Rows are claimed with SKIP LOCKED, so a second relay copy never sends
the same in-flight row. A failed batch backs off (2^attempts seconds, max 5 minutes); bookings never
wait on Kafka.
"""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import OutboxEvent

log = logging.getLogger(__name__)
BATCH = 100
MAX_BACKOFF_SECONDS = 300


class KafkaProducerAdapter:
    """Thin wrapper over confluent_kafka.Producer so the relay can be tested with a fake."""

    def __init__(self, config=None):
        from confluent_kafka import Producer

        self._producer = Producer(config or producer_config())
        self._failed = {}

    def produce(self, topic, key, value, event_id):
        def on_delivery(err, msg, event_id=event_id):
            if err is not None:
                self._failed[event_id] = str(err)[:200]

        self._producer.produce(topic, key=key.encode(), value=value, on_delivery=on_delivery,
                               headers={"event_id": event_id})

    def flush(self, timeout):
        """Wait for acks. Returns {event_id: error} for messages Kafka did not accept."""
        remaining = self._producer.flush(timeout)
        failed, self._failed = self._failed, {}
        if remaining:
            failed["*"] = f"{remaining} messages not acknowledged within {timeout} s"
        return failed


def producer_config():
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": settings.KAFKA_CLIENT_ID,
        "acks": "all",
        # Idempotent producer: retries inside librdkafka never create duplicates or reorder a partition.
        "enable.idempotence": True,
        "compression.type": "zstd",
        "linger.ms": 20,
        "delivery.timeout.ms": 30000,
    }


def _due(now):
    return (OutboxEvent.objects.filter(published_at__isnull=True)
            .filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)))


def publish_batch(producer, now=None, flush_timeout=10):
    """Publish up to BATCH due rows. Returns (published, failed)."""
    now = now or timezone.now()
    with transaction.atomic():
        rows = list(_due(now).select_for_update(skip_locked=True).order_by("id")[:BATCH])
        if not rows:
            return 0, 0
        for row in rows:
            producer.produce(row.topic, row.key, json.dumps(row.payload, separators=(",", ":")).encode(),
                             str(row.event_id))
        failed = producer.flush(flush_timeout)
        published_ids, failed_rows = [], []
        for row in rows:
            error = failed.get(str(row.event_id)) or failed.get("*")
            if error:
                row.attempts += 1
                row.last_error = error
                row.next_attempt_at = now + timedelta(seconds=min(2 ** row.attempts, MAX_BACKOFF_SECONDS))
                failed_rows.append(row)
            else:
                published_ids.append(row.pk)
        OutboxEvent.objects.filter(pk__in=published_ids).update(published_at=now, last_error="")
        if failed_rows:
            OutboxEvent.objects.bulk_update(failed_rows, ["attempts", "last_error", "next_attempt_at"])
            log.warning("Outbox relay: %d events not published, will retry", len(failed_rows))
    return len(published_ids), len(failed_rows)


def prune(now=None, keep_days=7):
    """Delete published rows older than keep_days. Unpublished rows are never deleted."""
    now = now or timezone.now()
    deleted, _ = OutboxEvent.objects.filter(published_at__lt=now - timedelta(days=keep_days)).delete()
    return deleted


def backlog(now=None):
    """Unpublished rows and the age of the oldest, for health checks and the dashboard."""
    now = now or timezone.now()
    oldest = OutboxEvent.objects.filter(published_at__isnull=True).order_by("id").values_list(
        "created_at", flat=True).first()
    return {
        "unpublished": OutboxEvent.objects.filter(published_at__isnull=True).count(),
        "oldest_seconds": int((now - oldest).total_seconds()) if oldest else 0,
    }
