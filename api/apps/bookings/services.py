"""Booking lifecycle. Every write to bookings, payments and the waitlist goes through here.

requested -> accepted -> advance_claimed -> confirmed -> completed
Exits: declined / expired (from requested), hold_expired (from accepted),
cancelled_passenger, cancelled_driver, no_show.

Anything that can change how many seats are taken locks the ride row first
(SELECT ... FOR UPDATE) and counts inside the same transaction.
"""
from datetime import timedelta
from urllib.parse import quote

from django.db import transaction
from django.utils import timezone

from apps.core import policy as calc
from apps.core.errors import Conflict, DomainError, Forbidden
from apps.core.models import audit
from apps.core.timefmt import hours_between, ist
from apps.notifications import services as notify
from apps.rides.models import Ride
from apps.rides.services import HOLDING
from apps.trust import services as trust
from apps.trust.models import ReliabilityEvent

from .models import Booking, NoShowCase, Payment, Reconfirmation, TripConfirmation, WaitlistEntry

S = Booking.Status
Kind = ReliabilityEvent.Kind


# ---------------------------------------------------------------- helpers

def _now():
    return timezone.now()


def _lock_ride(ride_id):
    return Ride.objects.select_for_update().select_related("city_pair", "driver", "policy_version").get(pk=ride_id)


def _lock_booking(booking_id):
    return Booking.objects.select_for_update().select_related(
        "ride", "ride__driver", "ride__city_pair", "passenger", "policy_version"
    ).get(pk=booking_id)


def _held(ride, exclude=None):
    qs = ride.bookings.filter(status__in=HOLDING)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.count()


def _open_offers(ride, now, exclude=None):
    qs = ride.waitlist.filter(status=WaitlistEntry.Status.OFFERED, offer_expires_at__gt=now)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.count()


def _confirmed(ride):
    return ride.bookings.filter(status=S.CONFIRMED).count()


def _route(ride):
    return f"{ride.city_pair.origin} to {ride.city_pair.destination}"


def _require_driver(booking, user):
    if booking.ride.driver_id != user.pk:
        raise Forbidden("Only the driver of this ride can do that.")


def _require_passenger(booking, user):
    if booking.passenger_id != user.pk:
        raise Forbidden("Only the passenger on this booking can do that.")


def upi_link(vpa, name, amount_inr, note):
    """upi://pay deep link. The app never holds money (hard rule 1)."""
    return f"upi://pay?pa={quote(vpa, safe='@')}&pn={quote(name)}&am={int(amount_inr)}&cu=INR&tn={quote(note)}"


def _create_refund(booking, amount, now):
    policy = booking.policy_version
    due_at = now + timedelta(hours=policy.refund_due_hours)
    payment = Payment.objects.create(
        booking=booking, kind=Payment.Kind.REFUND, amount_inr=amount, status=Payment.Status.DUE, due_at=due_at,
        dispute_at=due_at + timedelta(hours=policy.refund_dispute_after_hours),
    )
    ride = booking.ride
    notify.schedule(
        ride.driver, "refund_due", booking=booking, ride=ride, url=notify.booking_url(booking),
        title=f"Refund of Rs {amount} due",
        body=f"Please send Rs {amount} back to {booking.passenger.name} by {ist(due_at)}. "
             f"Booking {booking.code}.",
        dedupe_key=f"refund_due:{payment.pk}",
    )
    notify.schedule(
        booking.passenger, "refund_check", booking=booking, ride=ride, url=notify.booking_url(booking),
        send_at=due_at, title="Refund received?",
        body=f"Your driver should have sent Rs {amount} by {ist(due_at)}. Tap to confirm it arrived.",
        dedupe_key=f"refund_check:{payment.pk}",
    )
    return payment


# ---------------------------------------------------------------- requests

def request_seat(ride, passenger, *, note="", policy_ack=False):
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(ride.pk)
        policy = ride.policy_version
        if not passenger.profile_complete:
            raise DomainError("Finish your profile before requesting a seat.", "profile_incomplete")
        if not policy_ack:
            raise DomainError("Please agree to the cancellation policy to request a seat.", "policy_ack_required")
        if ride.status != Ride.Status.OPEN:
            raise DomainError("This ride is no longer taking requests.")
        if ride.driver_id == passenger.pk:
            raise DomainError("You can't request a seat on your own ride.")
        if trust.is_blocked(passenger, ride.driver):
            raise Forbidden("This ride isn't available to you.")
        if ride.women_only and not passenger.women_only_eligible:
            raise Forbidden("This is a women-only ride for verified members.", "women_only_ineligible")
        close_at = ride.departure_at - timedelta(hours=policy.request_close_hours)
        if now >= close_at:
            raise DomainError(f"Seat requests for this ride closed at {ist(close_at)}.")
        if Booking.objects.filter(ride=ride, passenger=passenger, status__in=Booking.ACTIVE).exists():
            raise Conflict("You already have a request on this ride.")
        if ride.seats_offered - _held(ride) - _open_offers(ride, now) <= 0:
            raise Conflict("This ride is full. You can join the waitlist.", "ride_full")
        booking = Booking.objects.create(
            ride=ride,
            passenger=passenger,
            policy_version=policy,
            note=note.strip()[:300],
            fare_inr=ride.fare_inr,
            advance_inr=ride.advance_inr,
            passenger_policy_ack_at=now,
            request_expires_at=min(now + timedelta(hours=policy.request_ttl_hours), close_at),
        )
        notify.schedule(
            ride.driver, "seat_requested", booking=booking, ride=ride, url=notify.ride_url(ride),
            title="New seat request",
            body=f"{passenger.name} from {passenger.hometown} asked for a seat on {_route(ride)}, {ist(ride.departure_at)}. "
                 f"Please reply by {ist(booking.request_expires_at)}.",
        )
        audit(passenger, "booking.requested", booking)
    return booking


def accept(booking, driver):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_driver(booking, driver)
        if booking.status == S.REQUESTED and booking.request_expires_at and booking.request_expires_at <= now:
            booking.status = S.EXPIRED
            booking.save(update_fields=["status", "updated_at"])
    with transaction.atomic():
        ride = _lock_ride(booking.ride_id)
        booking = _lock_booking(booking.pk)
        if booking.status == S.EXPIRED:
            raise Conflict("This request has expired.")
        if booking.status != S.REQUESTED:
            raise Conflict("This request is no longer waiting for a reply.")
        if ride.seats_offered - _held(ride) - _open_offers(ride, now) <= 0:
            raise Conflict("No seat is free to accept. Decline or wait for a cancellation.", "ride_full")
        policy = booking.policy_version
        booking.status = S.ACCEPTED
        booking.accepted_at = now
        booking.driver_policy_ack_at = now
        booking.hold_expires_at = min(now + timedelta(hours=policy.hold_hours), ride.departure_at)
        booking.save()
        _notify_accepted(booking)
        audit(driver, "booking.accepted", booking)
    return booking


def _notify_accepted(booking):
    ride = booking.ride
    notify.schedule(
        booking.passenger, "seat_accepted", booking=booking, ride=ride, url=notify.booking_url(booking),
        title="Seat accepted. Pay the advance to lock it",
        body=f"{ride.driver.name} accepted you on {_route(ride)}, {ist(ride.departure_at)}. "
             f"Pay Rs {booking.advance_inr} by {ist(booking.hold_expires_at)} or the hold lapses.",
    )


def decline(booking, driver):
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_driver(booking, driver)
        if booking.status != S.REQUESTED:
            raise Conflict("This request is no longer waiting for a reply.")
        booking.status = S.DECLINED
        booking.save(update_fields=["status", "updated_at"])
        notify.schedule(
            booking.passenger, "seat_declined", booking=booking, ride=booking.ride, url="/",
            title="Seat request declined",
            body=f"The driver can't take you on {_route(booking.ride)}. Other rides may still have seats.",
        )
    return booking


# ---------------------------------------------------------------- advance

def claim_advance(booking, passenger, *, utr=""):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_passenger(booking, passenger)
        if booking.status != S.ACCEPTED:
            raise Conflict("You can mark the advance as paid once the driver accepts.")
        if booking.hold_expires_at and booking.hold_expires_at <= now:
            raise Conflict("This hold has lapsed. Request the seat again if it is still free.", "hold_expired")
        booking.status = S.ADVANCE_CLAIMED
        booking.advance_claimed_at = now
        booking.save()
        Payment.objects.create(
            booking=booking, kind=Payment.Kind.ADVANCE, amount_inr=booking.advance_inr,
            status=Payment.Status.CLAIMED, claimed_at=now, utr=utr.strip()[:22],
        )
        notify.schedule(
            booking.ride.driver, "advance_claimed", booking=booking, ride=booking.ride,
            url=notify.booking_url(booking), title="Advance marked as paid",
            body=f"{passenger.name} says they paid Rs {booking.advance_inr} for booking {booking.code}. "
                 f"Check your UPI app, then tap Advance received.",
        )
    return booking


def confirm_advance(booking, driver):
    """Driver taps 'Advance received'. The only way a seat becomes confirmed."""
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(booking.ride_id)
        booking = _lock_booking(booking.pk)
        _require_driver(booking, driver)
        if booking.status not in (S.ACCEPTED, S.ADVANCE_CLAIMED):
            raise Conflict("This booking is not waiting for an advance.")
        if ride.status != Ride.Status.OPEN:
            raise Conflict("This ride is no longer open.")
        if ride.bookings.filter(status=S.CONFIRMED).exclude(pk=booking.pk).count() >= ride.seats_offered:
            raise Conflict("All seats are already confirmed.", "ride_full")
        booking.status = S.CONFIRMED
        booking.confirmed_at = now
        booking.save()
        advance = booking.payments.filter(kind=Payment.Kind.ADVANCE).first()
        if advance:
            advance.status = Payment.Status.CONFIRMED
            advance.confirmed_at = now
            advance.save(update_fields=["status", "confirmed_at"])
        else:
            Payment.objects.create(
                booking=booking, kind=Payment.Kind.ADVANCE, amount_inr=booking.advance_inr,
                status=Payment.Status.CONFIRMED, confirmed_at=now,
            )
        if booking.waitlist_entry_id:
            WaitlistEntry.objects.filter(pk=booking.waitlist_entry_id).update(status=WaitlistEntry.Status.ACCEPTED)
        _apply_refill(ride, booking, now)
        trip = f"Booking {booking.code}, {_route(ride)}, {ist(ride.departure_at)}."
        notify.schedule(
            booking.passenger, "booking_confirmed", booking=booking, ride=ride, url=notify.booking_url(booking),
            title="Seat confirmed", body=f"{trip} {notify.cutoff_text(booking)}",
        )
        notify.schedule(
            ride.driver, "booking_confirmed", booking=booking, ride=ride, url=notify.booking_url(booking),
            title="Passenger confirmed",
            body=f"{trip} {booking.passenger.name}'s phone number is now in the booking.",
        )
        notify.schedule_trip_reminders(booking)
        audit(driver, "booking.confirmed", booking)
    return booking


def _apply_refill(ride, new_booking, now):
    """A pending penalty cancellation is refilled when confirmed seats are back to where they were
    when that passenger cancelled (plan decision 4). Oldest first, one per new booking."""
    confirmed = _confirmed(ride)
    pending = ride.bookings.select_for_update().filter(
        status=S.CANCELLED_PASSENGER, refund_outcome=Booking.RefundOutcome.PENDING_REFILL, refilled_by__isnull=True
    ).order_by("cancelled_at")
    for cancelled in pending:
        if confirmed >= (cancelled.confirmed_seats_at_cancel or 0):
            cancelled.refund_outcome = Booking.RefundOutcome.FULL
            cancelled.refund_inr = cancelled.advance_inr
            cancelled.refilled_by = new_booking
            cancelled.save()
            _create_refund(cancelled, cancelled.advance_inr, now)
            notify.schedule(
                cancelled.passenger, "seat_refilled", booking=cancelled, ride=ride,
                url=notify.booking_url(cancelled), title="Your seat was refilled",
                body=f"Someone took your seat on {_route(ride)}, so your full advance of Rs {cancelled.advance_inr} comes back.",
            )
            return cancelled
    return None


# ---------------------------------------------------------------- cancellation

def cancel_by_passenger(booking, passenger):
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(booking.ride_id)
        booking = _lock_booking(booking.pk)
        _require_passenger(booking, passenger)
        if booking.status not in Booking.ACTIVE:
            raise Conflict("This booking can't be cancelled now.")
        if now >= ride.departure_at:
            raise Conflict("Departure has passed, so this booking can't be cancelled.")
        hours_left = hours_between(ride.departure_at, now)
        policy = booking.policy_version
        previous = booking.status
        confirmed_before = _confirmed(ride)
        booking.status = S.CANCELLED_PASSENGER
        booking.cancelled_at = now

        if previous == S.CONFIRMED:
            tier = calc.FULL if booking.free_cancel_any_time else calc.passenger_cancel_tier(
                hours_left, policy.full_refund_before_hours, policy.full_penalty_under_hours
            )
            if tier == calc.FULL:
                booking.refund_outcome = Booking.RefundOutcome.FULL
                booking.refund_inr = booking.advance_inr
                booking.save()
                _create_refund(booking, booking.advance_inr, now)
                kind = Kind.PASSENGER_EARLY_CANCEL
            else:
                booking.refund_outcome = Booking.RefundOutcome.PENDING_REFILL
                booking.penalty_tier = Booking.PenaltyTier.HALF if tier == calc.HALF else Booking.PenaltyTier.ALL
                booking.confirmed_seats_at_cancel = confirmed_before
                booking.save()
                kind = Kind.PASSENGER_LATE_CANCEL
            trust.record_event(passenger, kind, ride=ride, booking=booking, hours_before_departure=hours_left)
        elif previous == S.ADVANCE_CLAIMED:
            # Driver never confirmed receipt. If money did move, it all goes back.
            booking.refund_outcome = Booking.RefundOutcome.FULL
            booking.refund_inr = booking.advance_inr
            booking.save()
            booking.payments.filter(kind=Payment.Kind.ADVANCE).update(status=Payment.Status.VOID)
            _create_refund(booking, booking.advance_inr, now)
        else:
            booking.save()

        notify.cancel_pending(booking=booking, kinds=notify.TRIP_REMINDER_KINDS)
        notify.schedule(
            ride.driver, "passenger_cancelled", booking=booking, ride=ride, url=notify.ride_url(ride),
            title="A passenger cancelled",
            body=f"{passenger.name} cancelled booking {booking.code} on {_route(ride)}. "
                 f"The waitlist, if any, has been offered the seat.",
        )
        audit(passenger, "booking.cancelled", booking, previous=previous, hours_left=round(hours_left, 2))
        offer_waitlist(ride, now)
    return booking


def cancel_ride(ride, driver):
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(ride.pk)
        if ride.driver_id != driver.pk:
            raise Forbidden("Only the driver can cancel this ride.")
        if ride.status != Ride.Status.OPEN:
            raise Conflict("This ride is already closed.")
        if now >= ride.departure_at:
            raise Conflict("Departure has passed, so this ride can't be cancelled.")
        hours_left = hours_between(ride.departure_at, now)
        policy = ride.policy_version
        ride.status = Ride.Status.CANCELLED
        ride.cancelled_at = now
        ride.save()

        had_confirmed = False
        for booking in ride.bookings.select_for_update().filter(status__in=Booking.ACTIVE):
            previous = booking.status
            had_confirmed |= previous == S.CONFIRMED
            booking.status = S.CANCELLED_DRIVER
            booking.cancelled_at = now
            if previous in (S.ADVANCE_CLAIMED, S.CONFIRMED):
                booking.refund_outcome = Booking.RefundOutcome.FULL
                booking.refund_inr = booking.advance_inr
                booking.save()
                _create_refund(booking, booking.advance_inr, now)
            else:
                booking.save()
            notify.schedule(
                booking.passenger, "ride_cancelled", booking=booking, ride=ride, url="/",
                title="Your driver cancelled",
                body=f"The {_route(ride)} ride on {ist(ride.departure_at)} is cancelled."
                     + (f" Your full advance of Rs {booking.advance_inr} is due back." if booking.refund_inr else ""),
            )
        # Late cancellers still owe a full refund: the ride never left.
        for booking in ride.bookings.select_for_update().filter(refund_outcome=Booking.RefundOutcome.PENDING_REFILL):
            booking.refund_outcome = Booking.RefundOutcome.FULL
            booking.refund_inr = booking.advance_inr
            booking.save()
            _create_refund(booking, booking.advance_inr, now)

        ride.waitlist.filter(status__in=[WaitlistEntry.Status.WAITING, WaitlistEntry.Status.OFFERED]).update(
            status=WaitlistEntry.Status.EXPIRED
        )
        notify.cancel_pending(ride=ride, kinds=notify.TRIP_REMINDER_KINDS)
        if had_confirmed:
            late = hours_left < policy.driver_late_cancel_hours
            trust.record_event(
                driver, Kind.DRIVER_LATE_CANCEL if late else Kind.DRIVER_EARLY_CANCEL,
                ride=ride, hours_before_departure=hours_left,
            )
        audit(driver, "ride.cancelled", ride, hours_left=round(hours_left, 2))
    return ride


def reschedule(ride, driver, new_departure_at):
    """Moving departure by more than the tolerance after confirmation lets passengers cancel free
    and counts as a driver change."""
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(ride.pk)
        if ride.driver_id != driver.pk:
            raise Forbidden("Only the driver can change this ride.")
        if ride.status != Ride.Status.OPEN:
            raise Conflict("This ride is closed.")
        policy = ride.policy_version
        if new_departure_at < now + timedelta(hours=policy.min_post_lead_hours):
            raise DomainError(f"New departure must be at least {policy.min_post_lead_hours} hours from now.")
        shift_hours = abs(hours_between(new_departure_at, ride.departure_at))
        duration = ride.expected_arrival_at - ride.departure_at
        ride.departure_at = new_departure_at
        ride.expected_arrival_at = new_departure_at + duration
        ride.save()
        confirmed = list(ride.bookings.select_for_update().filter(status=S.CONFIRMED).select_related("passenger"))
        big_change = shift_hours > policy.reschedule_tolerance_hours
        for booking in confirmed:
            if big_change:
                booking.free_cancel_any_time = True
                booking.save(update_fields=["free_cancel_any_time", "updated_at"])
            notify.cancel_pending(booking=booking, kinds=notify.TRIP_REMINDER_KINDS)
            booking.ride = ride
            notify.schedule_trip_reminders(booking)
            notify.schedule(
                booking.passenger, "ride_rescheduled", booking=booking, ride=ride, url=notify.booking_url(booking),
                title="Departure time changed",
                body=f"Your {_route(ride)} ride now leaves {ist(new_departure_at)}."
                     + (" You can cancel with a full refund any time before departure." if big_change else ""),
            )
        if big_change and confirmed:
            trust.record_event(driver, Kind.DRIVER_CHANGE, ride=ride, note=f"Moved by {shift_hours:.1f} h")
        audit(driver, "ride.rescheduled", ride, shift_hours=round(shift_hours, 2))
    return ride


# ---------------------------------------------------------------- waitlist

def join_waitlist(ride, passenger):
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(ride.pk)
        if not passenger.profile_complete:
            raise DomainError("Finish your profile before joining a waitlist.", "profile_incomplete")
        if ride.status != Ride.Status.OPEN or now >= ride.departure_at:
            raise DomainError("This ride is no longer open.")
        if ride.driver_id == passenger.pk:
            raise DomainError("You can't join the waitlist for your own ride.")
        if trust.is_blocked(passenger, ride.driver):
            raise Forbidden("This ride isn't available to you.")
        if ride.women_only and not passenger.women_only_eligible:
            raise Forbidden("This is a women-only ride for verified members.", "women_only_ineligible")
        if ride.seats_offered - _held(ride) - _open_offers(ride, now) > 0:
            raise Conflict("A seat is still free. Request it directly.")
        if Booking.objects.filter(ride=ride, passenger=passenger, status__in=Booking.ACTIVE).exists():
            raise Conflict("You already have a booking on this ride.")
        entry, created = WaitlistEntry.objects.get_or_create(ride=ride, passenger=passenger)
        if not created:
            if entry.status in (WaitlistEntry.Status.WAITING, WaitlistEntry.Status.OFFERED):
                raise Conflict("You're already on this waitlist.")
            entry.status = WaitlistEntry.Status.WAITING
            entry.offered_at = entry.offer_expires_at = None
            entry.created_at = now  # back of the queue
            entry.save()
    return entry


def offer_waitlist(ride, now=None):
    """Offer each free seat to the next person waiting. Call with the ride row locked."""
    now = now or _now()
    ride.waitlist.filter(status=WaitlistEntry.Status.OFFERED, offer_expires_at__lte=now).update(
        status=WaitlistEntry.Status.EXPIRED
    )
    if ride.status != Ride.Status.OPEN or now >= ride.departure_at:
        return []
    policy = ride.policy_version
    free = ride.seats_offered - _held(ride) - _open_offers(ride, now)
    offered = []
    if free <= 0:
        return offered
    short = hours_between(ride.departure_at, now) < policy.request_close_hours
    minutes = policy.waitlist_offer_short_minutes if short else policy.waitlist_offer_minutes
    expires = min(now + timedelta(minutes=minutes), ride.departure_at)
    for entry in ride.waitlist.select_for_update().filter(status=WaitlistEntry.Status.WAITING).select_related(
        "passenger"
    ).order_by("created_at")[:free]:
        if trust.is_blocked(entry.passenger, ride.driver):
            continue
        entry.status = WaitlistEntry.Status.OFFERED
        entry.offered_at = now
        entry.offer_expires_at = expires
        entry.save()
        notify.schedule(
            entry.passenger, "waitlist_offer", ride=ride, url=notify.ride_url(ride),
            title="A seat opened up for you",
            body=f"A seat on {_route(ride)}, {ist(ride.departure_at)} is yours if you accept by {ist(expires)}.",
            dedupe_key=f"waitlist_offer:{entry.pk}:{int(now.timestamp())}",
        )
        offered.append(entry)
    return offered


def accept_waitlist_offer(entry, passenger, *, policy_ack=False):
    now = _now()
    with transaction.atomic():
        ride = _lock_ride(entry.ride_id)
        entry = WaitlistEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.passenger_id != passenger.pk:
            raise Forbidden("This offer is for someone else.")
        if entry.status == WaitlistEntry.Status.OFFERED and entry.offer_expires_at <= now:
            offer_waitlist(ride, now)  # expires this offer and passes the seat on
    with transaction.atomic():
        ride = _lock_ride(entry.ride_id)
        entry = WaitlistEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.status == WaitlistEntry.Status.EXPIRED:
            raise Conflict("This offer has expired and passed to the next person.", "offer_expired")
        if entry.status != WaitlistEntry.Status.OFFERED:
            raise Conflict("There is no open offer on this entry.")
        if not policy_ack:
            raise DomainError("Please agree to the cancellation policy to take the seat.", "policy_ack_required")
        if ride.status != Ride.Status.OPEN:
            raise Conflict("This ride is no longer open.")
        if ride.seats_offered - _held(ride) - _open_offers(ride, now, exclude=entry) <= 0:
            raise Conflict("That seat is no longer free.", "ride_full")
        policy = ride.policy_version
        booking = Booking.objects.create(
            ride=ride, passenger=passenger, policy_version=policy, note="From the waitlist",
            fare_inr=ride.fare_inr, advance_inr=ride.advance_inr,
            status=S.ACCEPTED, passenger_policy_ack_at=now,
            driver_policy_ack_at=ride.created_at,  # the driver agreed to the policy when posting
            accepted_at=now, hold_expires_at=min(now + timedelta(hours=policy.hold_hours), ride.departure_at),
            waitlist_entry=entry,
        )
        entry.status = WaitlistEntry.Status.ACCEPTED
        entry.save()
        _notify_accepted(booking)
        notify.schedule(
            ride.driver, "waitlist_taken", booking=booking, ride=ride, url=notify.ride_url(ride),
            title="Waitlist seat taken",
            body=f"{passenger.name} took the open seat on {_route(ride)}. Confirm once their advance arrives.",
        )
    return booking


def withdraw_waitlist(entry, passenger):
    with transaction.atomic():
        ride = _lock_ride(entry.ride_id)
        entry = WaitlistEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.passenger_id != passenger.pk:
            raise Forbidden("This waitlist entry is someone else's.")
        if entry.status not in (WaitlistEntry.Status.WAITING, WaitlistEntry.Status.OFFERED):
            raise Conflict("You're not on this waitlist any more.")
        was_offered = entry.status == WaitlistEntry.Status.OFFERED
        entry.status = WaitlistEntry.Status.WITHDRAWN
        entry.save()
        if was_offered:
            offer_waitlist(ride)
    return entry


# ---------------------------------------------------------------- during the trip

def reconfirm(booking, user, stage_hours, coming):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        ride = booking.ride
        if user.pk not in (ride.driver_id, booking.passenger_id):
            raise Forbidden()
        if booking.status != S.CONFIRMED:
            raise Conflict("Only confirmed bookings can be reconfirmed.")
        if stage_hours not in Reconfirmation.STAGES:
            raise DomainError("Choose a valid check-in.")
        if stage_hours == 72 and user.pk != booking.passenger_id:
            raise DomainError("The 72 hour check-in is for the passenger.")
        hours_left = hours_between(ride.departure_at, now)
        if not 0 < hours_left <= stage_hours:
            raise DomainError("This check-in isn't open right now.")
        if Reconfirmation.objects.filter(booking=booking, user=user, stage_hours=stage_hours).exists():
            raise Conflict("You already answered this check-in.")
        Reconfirmation.objects.create(booking=booking, user=user, stage_hours=stage_hours, coming=coming)
        other = ride.driver if user.pk == booking.passenger_id else booking.passenger
        if coming and user.pk == booking.passenger_id and booking.at_risk:
            booking.at_risk = False
            booking.save(update_fields=["at_risk", "updated_at"])
        if not coming:
            booking.at_risk = True
            booking.save(update_fields=["at_risk", "updated_at"])
            notify.schedule(
                other, "not_coming", booking=booking, ride=ride, url=notify.booking_url(booking),
                title=f"{user.name} may not travel",
                body=f"{user.name} said they may not make the {_route(ride)} ride on {ist(ride.departure_at)}. "
                     "Give them a call.",
            )
    return booking


def confirm_trip(booking, user, happened):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        ride = booking.ride
        if user.pk not in (ride.driver_id, booking.passenger_id):
            raise Forbidden()
        if booking.status != S.CONFIRMED:
            raise Conflict("Only confirmed trips can be checked.")
        if hasattr(booking, "no_show_case") and booking.no_show_case.status in ("pending", "disputed", "upheld"):
            raise Conflict("A no-show report is open on this booking.")
        if now < ride.expected_arrival_at:
            raise DomainError(f"Trip check opens at the expected arrival time, {ist(ride.expected_arrival_at)}.")
        if TripConfirmation.objects.filter(booking=booking, user=user).exists():
            raise Conflict("You already answered.")
        TripConfirmation.objects.create(booking=booking, user=user, happened=happened)
        answers = dict(booking.trip_confirmations.values_list("user_id", "happened"))
        if answers.get(ride.driver_id) is True and answers.get(booking.passenger_id) is True:
            booking.status = S.COMPLETED
            booking.completed_at = now
            booking.save()
            trust.record_event(booking.passenger, Kind.TRIP_COMPLETED, ride=ride, booking=booking)
            if not ride.driver.reliability_events.filter(kind=Kind.TRIP_COMPLETED, ride=ride).exists():
                trust.record_event(ride.driver, Kind.TRIP_COMPLETED, ride=ride, booking=booking)
            notify.cancel_pending(booking=booking, kinds=("trip_check", "trip_check_reminder"))
    return booking


def mark_no_show(booking, driver):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_driver(booking, driver)
        ride = booking.ride
        policy = booking.policy_version
        if booking.status != S.CONFIRMED:
            raise Conflict("Only a confirmed booking can be marked as a no-show.")
        opens = ride.departure_at + timedelta(minutes=policy.no_show_after_minutes)
        if now < opens:
            raise DomainError(f"You can mark a no-show from {ist(opens)}.")
        if booking.trip_confirmations.filter(happened=True).exists():
            raise Conflict("Someone already confirmed this trip happened.")
        if NoShowCase.objects.filter(booking=booking).exists():
            raise Conflict("A no-show is already recorded.")
        case = NoShowCase.objects.create(booking=booking, dispute_until=now + timedelta(hours=policy.no_show_dispute_hours))
        notify.schedule(
            booking.passenger, "no_show_marked", booking=booking, ride=ride, url=notify.booking_url(booking),
            title="Your driver marked you as a no-show",
            body=f"If you were there, dispute it by {ist(case.dispute_until)}. Otherwise the driver keeps the advance.",
        )
        audit(driver, "booking.no_show_marked", booking)
    return case


def dispute_no_show(booking, passenger, statement=""):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_passenger(booking, passenger)
        case = NoShowCase.objects.select_for_update().filter(booking=booking).first()
        if not case or case.status != NoShowCase.Status.PENDING:
            raise Conflict("There is no open no-show to dispute.")
        if now >= case.dispute_until:
            raise Conflict("The dispute window has closed.")
        case.status = NoShowCase.Status.DISPUTED
        case.disputed_at = now
        case.passenger_statement = statement.strip()[:1000]
        case.save()
        audit(passenger, "booking.no_show_disputed", booking)
    return case


def finalise_no_show(case, *, upheld, staff=None, note=""):
    """Called by the tick for undisputed cases, and by ops in Django admin for disputed ones."""
    now = _now()
    with transaction.atomic():
        case = NoShowCase.objects.select_for_update().select_related("booking", "booking__ride").get(pk=case.pk)
        if case.status not in (NoShowCase.Status.PENDING, NoShowCase.Status.DISPUTED):
            return case
        booking = _lock_booking(case.booking_id)
        case.status = NoShowCase.Status.UPHELD if upheld else NoShowCase.Status.OVERTURNED
        case.resolved_at = now
        case.resolution_note = note
        case.save()
        if upheld:
            booking.status = S.NO_SHOW
            booking.refund_outcome = Booking.RefundOutcome.NONE
            booking.refund_inr = 0
            booking.save()
            trust.record_event(booking.passenger, Kind.NO_SHOW, ride=booking.ride, booking=booking)
            notify.cancel_pending(booking=booking, kinds=notify.TRIP_REMINDER_KINDS)
        audit(staff, "booking.no_show_finalised", booking, upheld=upheld)
    return case


def confirm_refund_received(booking, passenger):
    now = _now()
    with transaction.atomic():
        booking = _lock_booking(booking.pk)
        _require_passenger(booking, passenger)
        refund = booking.payments.select_for_update().filter(kind=Payment.Kind.REFUND, status=Payment.Status.DUE).first()
        if not refund:
            raise Conflict("There is no refund waiting for confirmation.")
        refund.status = Payment.Status.CONFIRMED
        refund.confirmed_at = now
        refund.save()
        overdue = ReliabilityEvent.objects.filter(
            kind=Kind.REFUND_OVERDUE, booking=booking, reversed_by__isnull=True
        ).first()
        if overdue:
            trust.record_event(overdue.user, Kind.REFUND_RESOLVED, booking=booking, ride=booking.ride, reverses=overdue)
        notify.cancel_pending(booking=booking, kinds=("refund_check",))
    return booking


def report_participant(booking, reporter, reason, details=""):
    ride = booking.ride
    if reporter.pk not in (ride.driver_id, booking.passenger_id):
        raise Forbidden()
    reported = booking.passenger if reporter.pk == ride.driver_id else ride.driver
    return trust.report(reporter, reported, reason, details, booking=booking)


def block_participant(booking, blocker):
    ride = booking.ride
    if blocker.pk not in (ride.driver_id, booking.passenger_id):
        raise Forbidden()
    blocked = booking.passenger if blocker.pk == ride.driver_id else ride.driver
    trust.block(blocker, blocked)
    return blocked
