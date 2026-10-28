"""Time-driven state changes, run once a minute by the scheduler tick.

Each sweep claims rows with SKIP LOCKED so two workers never process the same row,
and is safe to run again (it only touches rows still in the triggering state).
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core import policy as calc
from apps.core.timefmt import ist
from apps.notifications import services as notify
from apps.rides.models import Ride
from apps.trust import services as trust
from apps.trust.models import ReliabilityEvent

from . import services
from .models import Booking, NoShowCase, Payment, WaitlistEntry

S = Booking.Status
BATCH = 100


def _claim(qs):
    return list(qs.select_for_update(skip_locked=True, of=("self",))[:BATCH])


def expire_requests(now):
    with transaction.atomic():
        rows = _claim(Booking.objects.filter(status=S.REQUESTED, request_expires_at__lte=now))
        for b in rows:
            b.status = S.EXPIRED
            b.save(update_fields=["status", "updated_at"])
            notify.schedule(
                b.passenger, "request_expired", booking=b, url="/", title="Seat request expired",
                body="The driver didn't reply in time. Other rides may still have seats.",
            )
    return len(rows)


def expire_holds(now):
    ride_ids = set()
    with transaction.atomic():
        rows = _claim(Booking.objects.filter(status=S.ACCEPTED, hold_expires_at__lte=now))
        for b in rows:
            b.status = S.HOLD_EXPIRED
            b.save(update_fields=["status", "updated_at"])
            ride_ids.add(b.ride_id)
            notify.schedule(
                b.passenger, "hold_expired", booking=b, url=f"/r/{b.ride.code}", title="Seat hold lapsed",
                body="The advance wasn't marked as paid in time, so the seat was released.",
            )
    for ride_id in ride_ids:
        _reoffer(ride_id, now)
    return len(rows)


def expire_offers(now):
    with transaction.atomic():
        ride_ids = set(
            WaitlistEntry.objects.filter(status=WaitlistEntry.Status.OFFERED, offer_expires_at__lte=now)
            .values_list("ride_id", flat=True)[:BATCH]
        )
    for ride_id in ride_ids:
        _reoffer(ride_id, now)
    return len(ride_ids)


def _reoffer(ride_id, now):
    with transaction.atomic():
        ride = Ride.objects.select_for_update(skip_locked=True).filter(pk=ride_id).first()
        if ride:
            services.offer_waitlist(ride, now)


def settle_departures(now):
    """At departure, penalty-tier cancellations that were not refilled are decided."""
    with transaction.atomic():
        rows = _claim(
            Booking.objects.filter(
                status=S.CANCELLED_PASSENGER,
                refund_outcome=Booking.RefundOutcome.PENDING_REFILL,
                ride__departure_at__lte=now,
            ).select_related("ride", "passenger", "policy_version")
        )
        for b in rows:
            tier = calc.HALF if b.penalty_tier == Booking.PenaltyTier.HALF else calc.ALL
            b.refund_inr = calc.refund_for_tier(b.advance_inr, tier)
            b.refund_outcome = Booking.RefundOutcome.HALF if tier == calc.HALF else Booking.RefundOutcome.NONE
            b.save()
            if b.refund_inr:
                services._create_refund(b, b.refund_inr, now)
            notify.schedule(
                b.passenger, "cancellation_settled", booking=b, url=f"/bookings/{b.code}",
                title="Cancellation settled",
                body=(f"Your seat wasn't refilled. Rs {b.refund_inr} of your advance comes back."
                      if b.refund_inr else "Your seat wasn't refilled, so the driver keeps the advance."),
            )
        Ride.objects.filter(status=Ride.Status.OPEN, departure_at__lte=now).update(status=Ride.Status.DEPARTED)
    return len(rows)


def flag_overdue_refunds(now):
    """A refund unconfirmed refund_dispute_after_hours past its due time is an open dispute."""
    with transaction.atomic():
        rows = _claim(
            Payment.objects.filter(
                kind=Payment.Kind.REFUND, status=Payment.Status.DUE,
                overdue_flagged_at__isnull=True, dispute_at__lte=now,
            ).select_related("booking__ride__driver")
        )
        flagged = 0
        for p in rows:
            p.overdue_flagged_at = now
            p.save(update_fields=["overdue_flagged_at"])
            trust.record_event(
                p.booking.ride.driver, ReliabilityEvent.Kind.REFUND_OVERDUE, booking=p.booking, ride=p.booking.ride,
                note=f"Rs {p.amount_inr} due {ist(p.due_at)}",
            )
            flagged += 1
    return flagged


def finalise_no_shows(now):
    with transaction.atomic():
        cases = _claim(NoShowCase.objects.filter(status=NoShowCase.Status.PENDING, dispute_until__lte=now))
    for case in cases:
        services.finalise_no_show(case, upheld=True, note="Not disputed within the window")
    return len(cases)


def run_all(now=None):
    now = now or timezone.now()
    return {
        "requests_expired": expire_requests(now),
        "holds_expired": expire_holds(now),
        "offers_rerun": expire_offers(now),
        "departures_settled": settle_departures(now),
        "refunds_overdue": flag_overdue_refunds(now),
        "no_shows_finalised": finalise_no_shows(now),
    }

