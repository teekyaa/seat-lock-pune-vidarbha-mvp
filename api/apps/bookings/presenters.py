"""JSON shapes for rides and bookings, tailored to who is looking.

Contact details (phone, car registration, pickup details) are only included for
confirmed co-travellers on the same ride (hard rule 3). The UPI deep link is shown
to a passenger holding an accepted seat, because paying needs it (plan decision 2).
"""
from datetime import timedelta

from django.utils import timezone

from apps.accounts.api import public_user
from apps.core import policy as calc
from apps.core.timefmt import ist
from apps.rides.services import availability

from .models import Booking, Payment
from .services import upi_link

S = Booking.Status
CONTACT_STATUSES = (S.CONFIRMED, S.COMPLETED, S.NO_SHOW)


def _dt(value):
    return {"utc": value.isoformat(), "ist": ist(value)} if value else None


def _cutoffs(departure_at, policy):
    c = calc.cutoffs(departure_at, policy.full_refund_before_hours, policy.full_penalty_under_hours)
    return {"full_refund_until": _dt(c.full_refund_until), "full_penalty_from": _dt(c.full_penalty_from)}


def _policy(policy):
    return {
        "label": policy.label,
        "summary": policy.summary,
        "advance_percent": policy.advance_percent,
        "hold_hours": policy.hold_hours,
        "refund_due_hours": policy.refund_due_hours,
    }


def is_co_traveller(ride, viewer):
    if viewer is None:
        return False
    if ride.driver_id == viewer.pk:
        return ride.bookings.filter(status__in=CONTACT_STATUSES).exists()
    return ride.bookings.filter(passenger=viewer, status__in=CONTACT_STATUSES).exists()


def ride_json(ride, viewer=None, *, detail=False):
    seats_left = availability(ride)
    data = {
        "code": ride.code,
        "origin": ride.city_pair.origin,
        "destination": ride.city_pair.destination,
        "departure_at": _dt(ride.departure_at),
        "expected_arrival_at": _dt(ride.expected_arrival_at),
        "pickup_point": ride.pickup_point,
        "dropoff_point": ride.dropoff_point,
        "seats_offered": ride.seats_offered,
        "seats_left": seats_left,
        "fare_inr": ride.fare_inr,
        "suggested_fare_inr": ride.suggested_fare_inr,
        "advance_inr": ride.advance_inr,
        "women_only": ride.women_only,
        "notes": ride.notes,
        "status": ride.status,
        "driver": public_user(ride.driver),
        "vehicle": {"make_model": ride.vehicle.make_model, "colour": ride.vehicle.colour},
    }
    if not detail:
        return data
    policy = ride.policy_version
    data["policy"] = _policy(policy)
    data["cutoffs"] = _cutoffs(ride.departure_at, policy)
    data["requests_close_at"] = _dt(ride.departure_at - timedelta(hours=policy.request_close_hours))
    viewer_info = {"is_driver": False, "booking_code": None, "waitlist": None}
    if viewer is not None:
        viewer_info["is_driver"] = ride.driver_id == viewer.pk
        active = ride.bookings.filter(passenger=viewer, status__in=(*Booking.ACTIVE, S.COMPLETED, S.NO_SHOW)).first()
        viewer_info["booking_code"] = active.code if active else None
        entry = ride.waitlist.filter(passenger=viewer).first()
        if entry:
            viewer_info["waitlist"] = {"id": entry.pk, "status": entry.status, "offer_expires_at": _dt(entry.offer_expires_at)}
    data["viewer"] = viewer_info
    if is_co_traveller(ride, viewer):
        data["private"] = {
            "driver_phone": ride.driver.phone,
            "registration": ride.vehicle.registration,
            "pickup_details": ride.pickup_details,
        }
    return data


def _refund(booking):
    p = booking.payments.filter(kind=Payment.Kind.REFUND).order_by("-created_at").first()
    if not p:
        return None
    return {"amount_inr": p.amount_inr, "status": p.status, "due_at": _dt(p.due_at), "dispute_at": _dt(p.dispute_at),
            "confirmed_at": _dt(p.confirmed_at), "overdue": bool(p.overdue_flagged_at)}


def available_actions(booking, viewer, now=None):
    """Hints for the UI. The services re-check every rule, so this can never grant anything."""
    now = now or timezone.now()
    ride = booking.ride
    policy = booking.policy_version
    is_driver = viewer.pk == ride.driver_id
    is_passenger = viewer.pk == booking.passenger_id
    actions = []
    st = booking.status
    if is_driver and st == S.REQUESTED:
        actions += ["accept", "decline"]
    if is_passenger and st == S.ACCEPTED and booking.hold_expires_at and booking.hold_expires_at > now:
        actions.append("claim-advance")
    if is_driver and st in (S.ACCEPTED, S.ADVANCE_CLAIMED):
        actions.append("confirm-advance")
    if is_passenger and st in Booking.ACTIVE and now < ride.departure_at:
        actions.append("cancel")
    if st == S.CONFIRMED and now < ride.departure_at:
        hours_left = (ride.departure_at - now).total_seconds() / 3600
        answered = set(booking.reconfirmations.filter(user=viewer).values_list("stage_hours", flat=True))
        for stage in (12, 48, 72):
            if hours_left <= stage and stage not in answered and (stage != 72 or is_passenger):
                actions.append(f"reconfirm-{stage}")
                break
    no_show = booking.no_show_case if hasattr(booking, "no_show_case") else None
    if st == S.CONFIRMED and now >= ride.expected_arrival_at and not no_show \
            and not booking.trip_confirmations.filter(user=viewer).exists():
        actions.append("trip-confirmation")
    if is_driver and st == S.CONFIRMED and not no_show \
            and now >= ride.departure_at + timedelta(minutes=policy.no_show_after_minutes):
        actions.append("no-show")
    if is_passenger and no_show and no_show.status == "pending" and now < no_show.dispute_until:
        actions.append("dispute-no-show")
    if is_passenger and booking.payments.filter(kind=Payment.Kind.REFUND, status=Payment.Status.DUE).exists():
        actions.append("refund-received")
    if st not in (S.REQUESTED,):
        actions += ["report", "block"]
    return actions


def booking_json(booking, viewer):
    ride = booking.ride
    policy = booking.policy_version
    is_driver = viewer.pk == ride.driver_id
    now = timezone.now()
    no_show = booking.no_show_case if hasattr(booking, "no_show_case") else None
    data = {
        "code": booking.code,
        "status": booking.status,
        "status_label": booking.get_status_display(),
        "role": "driver" if is_driver else "passenger",
        "ride": ride_json(ride, viewer),
        "ride_code": ride.code,
        "passenger": public_user(booking.passenger),
        "note": booking.note,
        "fare_inr": booking.fare_inr,
        "advance_inr": booking.advance_inr,
        "policy": _policy(policy),
        "cutoffs": None if booking.free_cancel_any_time else _cutoffs(ride.departure_at, policy),
        "free_cancel_any_time": booking.free_cancel_any_time,
        "at_risk": booking.at_risk,
        "request_expires_at": _dt(booking.request_expires_at),
        "hold_expires_at": _dt(booking.hold_expires_at),
        "confirmed_at": _dt(booking.confirmed_at),
        "cancelled_at": _dt(booking.cancelled_at),
        "refund_outcome": booking.refund_outcome or None,
        "penalty_tier": booking.penalty_tier or None,
        "refund_inr": booking.refund_inr,
        "refund": _refund(booking),
        "reconfirmations": [
            {"stage_hours": r.stage_hours, "who": "driver" if r.user_id == ride.driver_id else "passenger",
             "coming": r.coming, "at": _dt(r.responded_at)}
            for r in booking.reconfirmations.all()
        ],
        "trip_confirmations": [
            {"who": "driver" if t.user_id == ride.driver_id else "passenger", "happened": t.happened}
            for t in booking.trip_confirmations.all()
        ],
        "no_show": {"status": no_show.status, "dispute_until": _dt(no_show.dispute_until)} if no_show else None,
        "actions": available_actions(booking, viewer, now),
    }
    if not is_driver and booking.status == S.ACCEPTED and ride.driver.upi_id:
        data["pay"] = {
            "upi_link": upi_link(ride.driver.upi_id, ride.driver.name, booking.advance_inr, booking.code),
            "amount_inr": booking.advance_inr,
            "pay_by": _dt(booking.hold_expires_at),
        }
    refund = data["refund"]
    if is_driver and refund and refund["status"] == Payment.Status.DUE and booking.passenger.upi_id:
        data["refund_pay"] = {
            "upi_link": upi_link(booking.passenger.upi_id, booking.passenger.name, refund["amount_inr"],
                                 f"Refund {booking.code}"),
            "amount_inr": refund["amount_inr"],
        }
    if booking.status in CONTACT_STATUSES:
        if is_driver:
            data["contact"] = {"phone": booking.passenger.phone}
        else:
            data["contact"] = {
                "phone": ride.driver.phone,
                "registration": ride.vehicle.registration,
                "pickup_details": ride.pickup_details,
            }
    elif refund and refund["status"] == Payment.Status.DUE:
        # Money is owed back, so the two people need to be able to reach each other.
        data["contact"] = {"phone": booking.passenger.phone if is_driver else ride.driver.phone}
    return data
