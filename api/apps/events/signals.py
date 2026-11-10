"""Capture domain events where state is saved.

Every booking and ride status change goes through Model.save() inside a service transaction, so a
post_save hook writes the outbox row in that same transaction: both commit or neither does. The
pre-save value is snapshotted on load (post_init) to tell real transitions from other saves.

Known gap: Ride.objects.update(status=DEPARTED) in the sweep bypasses save(), so "departed" is not
an event. Departure time is already on ride.posted / ride.rescheduled.
"""
from django.db.models.signals import post_init, post_save
from django.dispatch import receiver

from apps.accounts.models import OTPAbuseFlag
from apps.bookings.models import Booking
from apps.rides.models import Ride
from apps.trust.models import ReliabilityEvent

from .outbox import TOPIC_AUTH, TOPIC_BOOKINGS, TOPIC_RIDES, TOPIC_TRUST, emit


def _iso(value):
    return value.isoformat() if value else None


@receiver(post_init, sender=Booking)
@receiver(post_init, sender=Ride)
@receiver(post_init, sender=OTPAbuseFlag)
def _snapshot(sender, instance, **kwargs):
    # __dict__ avoids loading deferred fields.
    instance._event_snapshot = {
        "status": instance.__dict__.get("status"),
        "departure_at": instance.__dict__.get("departure_at"),
        "blocked_until": instance.__dict__.get("blocked_until"),
    }


def _refresh_snapshot(instance):
    _snapshot(type(instance), instance)


@receiver(post_save, sender=Booking)
def booking_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    before = instance._event_snapshot["status"]
    if created or before != instance.status:
        ride = instance.ride
        emit(TOPIC_BOOKINGS, ride.code, f"booking.{instance.status}", "booking", instance.code, {
            "booking": instance.code,
            "ride": ride.code,
            "status": instance.status,
            "previous_status": None if created else before,
            "seat_role": instance.role,
            "fare_inr": instance.fare_inr,
            "advance_inr": instance.advance_inr,
            "refund_outcome": instance.refund_outcome or None,
        })
    _refresh_snapshot(instance)


@receiver(post_save, sender=Ride)
def ride_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    snapshot = instance._event_snapshot
    data = {
        "ride": instance.code,
        "status": instance.status,
        "departure_at": _iso(instance.departure_at),
        "seats_offered": instance.seats_offered,
        "fare_inr": instance.fare_inr,
        "advance_required": instance.advance_required,
        "route_id": instance.route_id,
        "from_place_id": instance.from_place_id,
        "to_place_id": instance.to_place_id,
        "city_pair_id": instance.city_pair_id,
    }
    if created:
        emit(TOPIC_RIDES, instance.code, "ride.posted", "ride", instance.code, data)
    else:
        if snapshot["status"] != instance.status:
            emit(TOPIC_RIDES, instance.code, f"ride.{instance.status}", "ride", instance.code,
                 {**data, "previous_status": snapshot["status"]})
        if snapshot["departure_at"] and snapshot["departure_at"] != instance.departure_at:
            emit(TOPIC_RIDES, instance.code, "ride.rescheduled", "ride", instance.code,
                 {**data, "previous_departure_at": _iso(snapshot["departure_at"])})
    _refresh_snapshot(instance)


@receiver(post_save, sender=ReliabilityEvent)
def reliability_recorded(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return  # append-only: corrections arrive as new rows
    emit(TOPIC_TRUST, instance.user_id, "trust.reliability_recorded", "user", instance.user_id, {
        "user": str(instance.user_id),
        "kind": instance.kind,
        "ride_id": instance.ride_id,
        "booking_id": instance.booking_id,
        "reverses_id": instance.reverses_id,
    })


@receiver(post_save, sender=OTPAbuseFlag)
def otp_flag_changed(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    before = instance._event_snapshot["blocked_until"]
    if instance.blocked_until and instance.blocked_until != before:
        # The phone number or IP itself never goes on the log; the flag id points back to it.
        emit(TOPIC_AUTH, instance.pk, "auth.otp_blocked", "otp_flag", instance.pk, {
            "flag_id": instance.pk,
            "subject_kind": instance.kind,
            "reason": instance.reason,
            "blocked_until": _iso(instance.blocked_until),
            "times_blocked": instance.times_blocked,
        })
    _refresh_snapshot(instance)
