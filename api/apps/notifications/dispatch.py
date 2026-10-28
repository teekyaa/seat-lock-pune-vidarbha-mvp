"""Claim due notification rows with SKIP LOCKED, send, mark sent."""
import logging

from django.db import transaction
from django.utils import timezone

from apps.core.timefmt import ist

from . import channels
from . import services as notify
from .models import Notification

log = logging.getLogger(__name__)
BATCH = 50
MAX_ATTEMPTS = 3


def _still_relevant(n):
    """Messages are written when scheduled; whether they still matter is decided at send time."""
    b = n.booking
    if n.kind in notify.TRIP_REMINDER_KINDS:
        if b is None or b.status != "confirmed":
            return False
        if n.kind in ("still_coming_72", "reconfirm_48", "reconfirm_12"):
            stage = int(n.kind.rsplit("_", 1)[1])
            return not b.reconfirmations.filter(user=n.user, stage_hours=stage).exists()
        if n.kind == "trip_check_reminder":
            return not b.trip_confirmations.filter(user=n.user).exists()
        if n.kind == "mark_no_show":
            return not b.trip_confirmations.filter(happened=True).exists()
    if n.kind == "refund_check":
        return b is not None and b.payments.filter(kind="refund", status="due").exists()
    return True


def _reconfirm_48_check(n):
    """6 h after the 48 h reconfirm: if the passenger hasn't said yes, flag the seat and alert the waitlist."""
    b = n.booking
    if b.reconfirmations.filter(user=b.passenger, stage_hours__in=(72, 48), coming=True).exists():
        return
    b.at_risk = True
    b.save(update_fields=["at_risk", "updated_at"])
    ride = b.ride
    notify.schedule(
        ride.driver, "seat_at_risk", booking=b, ride=ride, url=notify.booking_url(b),
        title="Passenger hasn't reconfirmed",
        body=f"{b.passenger.name} hasn't reconfirmed for {ist(ride.departure_at)}. You can call them from the booking.",
    )
    for entry in ride.waitlist.filter(status="waiting").select_related("passenger"):
        notify.schedule(
            entry.passenger, "waitlist_heads_up", ride=ride, url=notify.ride_url(ride),
            title="A seat may open up",
            body=f"A passenger on {ride.city_pair.origin} to {ride.city_pair.destination}, {ist(ride.departure_at)} "
                 "hasn't reconfirmed. Keep an eye out for an offer.",
            dedupe_key=f"waitlist_heads_up:{b.pk}:{entry.pk}",
        )


def _deliver(n):
    errors, sent = [], ["in_app"]
    for name, fn in (("email", channels.send_email), ("push", channels.send_push)):
        try:
            if fn(n):
                sent.append(name)
        except Exception as exc:  # one channel failing must not block the others
            errors.append(f"{name}: {exc}")
            log.exception("Notification %s failed on %s", n.pk, name)
    return sent, errors


def dispatch_due(now=None):
    now = now or timezone.now()
    processed = 0
    while True:
        with transaction.atomic():
            rows = list(
                Notification.objects.select_for_update(skip_locked=True, of=("self",))
                .filter(status=Notification.Status.PENDING, send_at__lte=now)
                .select_related("user", "booking", "booking__ride", "booking__passenger")
                .order_by("send_at")[:BATCH]
            )
            if not rows:
                return processed
            for n in rows:
                processed += 1
                n.attempts += 1
                if not _still_relevant(n):
                    n.status = Notification.Status.SKIPPED
                    n.save(update_fields=["status", "attempts"])
                    continue
                if n.kind == "reconfirm_48_check":
                    _reconfirm_48_check(n)
                    n.status = Notification.Status.SENT
                    n.sent_at = now
                    n.save(update_fields=["status", "attempts", "sent_at"])
                    continue
                sent, errors = _deliver(n)
                n.channels_sent = sent
                n.last_error = "\n".join(errors)
                n.status = Notification.Status.SENT
                n.sent_at = now
                n.save(update_fields=["status", "attempts", "sent_at", "channels_sent", "last_error"])
