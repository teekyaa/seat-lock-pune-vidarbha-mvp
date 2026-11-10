"""Event consumers. Each handler is idempotent: it records (consumer, event_id) in the same DB
transaction as its effect, so a replayed message changes nothing. Kafka offsets are committed only
after that transaction commits (see the run_event_consumer command).
"""
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F

from .models import DailyMetric, ProcessedEvent
from .outbox import TOPICS

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Event type -> metric name. Unknown types are acknowledged and skipped, so producers can add new
# events before this consumer learns about them.
METRICS = {
    "ride.posted": "rides_posted",
    "ride.cancelled": "rides_cancelled",
    "ride.rescheduled": "rides_rescheduled",
    "booking.requested": "seat_requests",
    "booking.accepted": "seat_requests_accepted",
    "booking.declined": "seat_requests_declined",
    "booking.expired": "seat_requests_expired",
    "booking.hold_expired": "holds_expired",
    "booking.confirmed": "seats_confirmed",
    "booking.completed": "trips_completed",
    "booking.cancelled_passenger": "passenger_cancellations",
    "booking.cancelled_driver": "driver_cancelled_seats",
    "booking.no_show": "no_shows",
    "auth.otp_blocked": "otp_blocks",
}


class PoisonMessage(Exception):
    """The message can never be processed (bad JSON or envelope). Logged and skipped."""


def parse(raw):
    try:
        event = json.loads(raw)
        event_id, event_type, occurred = event["event_id"], event["type"], event["occurred_at"]
        datetime.fromisoformat(occurred)
    except (ValueError, KeyError, TypeError) as exc:
        raise PoisonMessage(str(exc)[:200]) from None
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        raise PoisonMessage("event_id and type must be strings")
    return event


def _metric_names(event):
    names = []
    if event["type"] in METRICS:
        names.append(METRICS[event["type"]])
    if event["type"] == "trust.reliability_recorded":
        kind = (event.get("data") or {}).get("kind")
        if isinstance(kind, str) and kind.isidentifier():
            names.append(f"reliability_{kind}")
    return names


def apply_metrics(event, consumer="metrics"):
    """Count the event into DailyMetric once. Returns False for a duplicate."""
    day = datetime.fromisoformat(event["occurred_at"]).astimezone(IST).date()
    try:
        with transaction.atomic():
            ProcessedEvent.objects.create(consumer=consumer, event_id=event["event_id"])
            for name in _metric_names(event):
                metric, created = DailyMetric.objects.get_or_create(day=day, name=name, defaults={"count": 1})
                if not created:
                    DailyMetric.objects.filter(pk=metric.pk).update(count=F("count") + 1)
    except IntegrityError:
        return False  # already processed: the unique (consumer, event_id) row exists
    return True


def consumer_config(group_id):
    return {
        "bootstrap.servers": settings.KAFKA_BOOTSTRAP_SERVERS,
        "client.id": settings.KAFKA_CLIENT_ID,
        "group.id": group_id,
        "enable.auto.commit": False,  # commit only after the DB transaction commits
        "auto.offset.reset": "earliest",
        "isolation.level": "read_committed",
    }


def subscribed_topics():
    return list(TOPICS)
