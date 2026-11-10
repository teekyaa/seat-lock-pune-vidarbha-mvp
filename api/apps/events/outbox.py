"""Write domain events to the outbox. Call inside the transaction that makes the change."""
from django.conf import settings
from django.utils import timezone

from .models import OutboxEvent

TOPIC_BOOKINGS = "seatlock.bookings.v1"
TOPIC_RIDES = "seatlock.rides.v1"
TOPIC_TRUST = "seatlock.trust.v1"
TOPIC_AUTH = "seatlock.auth.v1"
TOPICS = (TOPIC_BOOKINGS, TOPIC_RIDES, TOPIC_TRUST, TOPIC_AUTH)
SCHEMA_VERSION = 1


def emit(topic, key, event_type, aggregate_type, aggregate_id, data, occurred_at=None):
    """Queue one event. Returns the row, or None when events are switched off (local development).

    data must hold ids, codes, statuses and integer rupees only: never phone numbers, UPI IDs,
    names or registrations (CLAUDE.md hard rule 3). The log is retained and replayed.
    """
    if not settings.EVENTS_OUTBOX_ENABLED:
        return None
    occurred_at = occurred_at or timezone.now()
    event = OutboxEvent(topic=topic, key=str(key)[:64], type=event_type, occurred_at=occurred_at, payload={})
    event.payload = {
        "event_id": str(event.event_id),
        "type": event_type,
        "version": SCHEMA_VERSION,
        "occurred_at": occurred_at.isoformat(),
        "aggregate": {"type": aggregate_type, "id": str(aggregate_id)},
        "data": data,
    }
    event.save()
    return event
