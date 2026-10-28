"""Notification rows. Nothing here sends; the per-minute tick does (see dispatch.py)."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.policy import cutoffs
from apps.core.timefmt import ist

from .models import Notification


def schedule(user, kind, *, title, body, send_at=None, url="", booking=None, ride=None, dedupe_key=None):
    """Create a notification row. A repeated dedupe_key is ignored, so callers can be idempotent."""
    try:
        with transaction.atomic():
            return Notification.objects.create(
                user=user,
                kind=kind,
                title=title,
                body=body,
                url=url,
                booking=booking,
                ride=ride,
                send_at=send_at or timezone.now(),
                dedupe_key=dedupe_key,
            )
    except IntegrityError:
        if dedupe_key is None:
            raise
        return Notification.objects.get(dedupe_key=dedupe_key)


def cancel_pending(*, booking=None, ride=None, kinds=None):
    qs = Notification.objects.filter(status=Notification.Status.PENDING)
    if booking is not None:
        qs = qs.filter(booking=booking)
    if ride is not None:
        qs = qs.filter(ride=ride)
    if kinds:
        qs = qs.filter(kind__in=kinds)
    return qs.update(status=Notification.Status.SKIPPED, last_error="Cancelled: no longer relevant")


def booking_url(booking):
    return f"/bookings/{booking.code}"


def ride_url(ride):
    return f"/r/{ride.code}"


def cutoff_text(booking):
    if booking.free_cancel_any_time:
        return "The driver moved the departure, so you can cancel with a full refund until departure."
    policy = booking.policy_version
    c = cutoffs(booking.ride.departure_at, policy.full_refund_before_hours, policy.full_penalty_under_hours)
    return (
        f"Cancel before {ist(c.full_refund_until)} for a full refund. "
        f"From then until {ist(c.full_penalty_from)} the driver keeps half the advance. "
        f"After that the driver keeps all of it, unless your seat is refilled."
    )


TRIP_REMINDER_KINDS = (
    "still_coming_72",
    "reconfirm_48",
    "reconfirm_48_check",
    "reconfirm_12",
    "mark_no_show",
    "trip_check",
    "trip_check_reminder",
)


def schedule_trip_reminders(booking):
    """The notification schedule from CLAUDE.md, relative to departure. Past times are skipped."""
    ride = booking.ride
    dep = ride.departure_at
    now = timezone.now()
    driver, passenger = ride.driver, booking.passenger
    route = f"{ride.city_pair.origin} to {ride.city_pair.destination}"
    when = ist(dep)
    url = booking_url(booking)
    key = f"{booking.code}:{int(dep.timestamp())}"

    plan = [
        (passenger, "still_coming_72", dep - timedelta(hours=72), "Still coming?",
         f"Your {route} ride leaves {when}. Tap to tell your driver you are still coming."),
        (passenger, "reconfirm_48", dep - timedelta(hours=48), "Please reconfirm your seat",
         f"Your {route} ride leaves {when}. {cutoff_text(booking)}"),
        (driver, "reconfirm_48", dep - timedelta(hours=48), "Please reconfirm the ride",
         f"Your {route} ride leaves {when}. Tap to confirm you are still driving."),
        (driver, "reconfirm_48_check", dep - timedelta(hours=42), "", ""),
        (passenger, "reconfirm_12", dep - timedelta(hours=12), "Ride tomorrow: pickup details",
         f"Your {route} ride leaves {when}. Open the booking for pickup details and to reconfirm."),
        (driver, "reconfirm_12", dep - timedelta(hours=12), "Ride soon: reconfirm",
         f"Your {route} ride leaves {when}. Your passenger list and phone numbers are in the app."),
        (driver, "mark_no_show", dep + timedelta(minutes=ride.policy_version.no_show_after_minutes),
         "Did everyone turn up?", "If a passenger did not turn up, you can mark a no-show now."),
        (passenger, "trip_check", ride.expected_arrival_at, "Did this trip happen?",
         f"Tell us if your {route} trip happened. It builds both your records."),
        (driver, "trip_check", ride.expected_arrival_at, "Did this trip happen?",
         f"Tell us if your {route} trip happened with {passenger.name}."),
        (passenger, "trip_check_reminder", ride.expected_arrival_at + timedelta(hours=24), "Did this trip happen?",
         "A quick yes or no keeps your record accurate."),
        (driver, "trip_check_reminder", ride.expected_arrival_at + timedelta(hours=24), "Did this trip happen?",
         "A quick yes or no keeps your record accurate."),
    ]
    for user, kind, send_at, title, body in plan:
        if send_at <= now:
            continue
        schedule(
            user, kind, title=title, body=body, send_at=send_at, url=url, booking=booking, ride=ride,
            dedupe_key=f"{kind}:{key}:{user.pk}",
        )
