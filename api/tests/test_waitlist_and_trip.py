"""Waitlist offers, reconfirmation, trip confirmation, no-shows and refund disputes."""
from datetime import timedelta

import pytest

from apps.bookings import services, sweeps
from apps.bookings.models import Booking, NoShowCase, WaitlistEntry
from apps.core.errors import Conflict, DomainError
from apps.trust.models import ReliabilityEvent
from apps.trust.services import refresh_reliability_view, reliability_for

S = Booking.Status
K = ReliabilityEvent.Kind
W = WaitlistEntry.Status


@pytest.fixture
def full_ride(make_ride, rahul, confirm):
    ride = make_ride(seats=1)
    booking = confirm(ride, rahul)
    return ride, booking


def test_waitlist_only_when_full(ride, neha):
    with pytest.raises(Conflict):
        services.join_waitlist(ride, neha)


def test_cancellation_offers_seat_to_waitlist(full_ride, rahul, neha, sam, clock):
    ride, booking = full_ride
    first = services.join_waitlist(ride, neha)
    second = services.join_waitlist(ride, sam)
    services.cancel_by_passenger(booking, rahul)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == W.OFFERED and second.status == W.WAITING
    assert first.offer_expires_at == clock.now + timedelta(minutes=120)
    # The offer reserves the seat against direct requests
    from apps.accounts.models import User
    other = User.objects.create_user("+919000000009", name="Other", hometown="Pune", terms_accepted_at=clock.now)
    with pytest.raises(Conflict):
        services.request_seat(ride, other, policy_ack=True)


def test_accepting_offer_creates_hold_and_refill(full_ride, rahul, neha, clock):
    ride, booking = full_ride
    entry = services.join_waitlist(ride, neha)
    clock.set(ride.departure_at - timedelta(hours=30))
    services.cancel_by_passenger(booking, rahul)
    new = services.accept_waitlist_offer(entry, neha, policy_ack=True)
    assert new.status == S.ACCEPTED and new.waitlist_entry_id == entry.pk
    services.confirm_advance(new, ride.driver)
    booking.refresh_from_db()
    assert booking.refund_outcome == Booking.RefundOutcome.FULL


def test_expired_offer_passes_to_next(full_ride, rahul, neha, sam, clock):
    ride, booking = full_ride
    first = services.join_waitlist(ride, neha)
    second = services.join_waitlist(ride, sam)
    services.cancel_by_passenger(booking, rahul)
    clock.advance(minutes=121)
    with pytest.raises(Conflict):
        services.accept_waitlist_offer(first, neha, policy_ack=True)
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == W.EXPIRED and second.status == W.OFFERED


def test_sweep_passes_expired_offer_on(full_ride, rahul, neha, sam, clock):
    ride, booking = full_ride
    services.join_waitlist(ride, neha)
    second = services.join_waitlist(ride, sam)
    services.cancel_by_passenger(booking, rahul)
    clock.advance(minutes=121)
    sweeps.run_all(clock.now)
    second.refresh_from_db()
    assert second.status == W.OFFERED


def test_short_offer_inside_12h(full_ride, rahul, neha, clock):
    ride, booking = full_ride
    entry = services.join_waitlist(ride, neha)
    clock.set(ride.departure_at - timedelta(hours=6))
    services.cancel_by_passenger(booking, rahul)
    entry.refresh_from_db()
    assert entry.offer_expires_at == clock.now + timedelta(minutes=30)


def test_reconfirm_windows(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    with pytest.raises(DomainError):
        services.reconfirm(b, rahul, 72, True)  # 100 h out, not open yet
    clock.set(ride.departure_at - timedelta(hours=60))
    services.reconfirm(b, rahul, 72, True)
    with pytest.raises(DomainError):
        services.reconfirm(b, ride.driver, 72, True)  # 72 h check is passenger only
    with pytest.raises(Conflict):
        services.reconfirm(b, rahul, 72, True)


def test_not_coming_flags_at_risk(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=40))
    services.reconfirm(b, rahul, 48, False)
    b.refresh_from_db()
    assert b.at_risk


def test_trip_completed_when_both_say_yes(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    with pytest.raises(DomainError):
        services.confirm_trip(b, rahul, True)  # before expected arrival
    clock.set(ride.expected_arrival_at)
    services.confirm_trip(b, rahul, True)
    b.refresh_from_db()
    assert b.status == S.CONFIRMED
    services.confirm_trip(b, ride.driver, True)
    b.refresh_from_db()
    assert b.status == S.COMPLETED
    assert ReliabilityEvent.objects.filter(kind=K.TRIP_COMPLETED).count() == 2


def test_conflicting_trip_answers_are_not_counted(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.expected_arrival_at)
    services.confirm_trip(b, rahul, True)
    services.confirm_trip(b, ride.driver, False)
    b.refresh_from_db()
    assert b.status == S.CONFIRMED
    assert not ReliabilityEvent.objects.filter(kind=K.TRIP_COMPLETED).exists()


def test_no_show_window_and_finalise(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at + timedelta(minutes=29))
    with pytest.raises(DomainError):
        services.mark_no_show(b, ride.driver)
    clock.set(ride.departure_at + timedelta(minutes=30))
    case = services.mark_no_show(b, ride.driver)
    assert case.dispute_until == clock.now + timedelta(hours=24)
    clock.advance(hours=24)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.status == S.NO_SHOW and b.refund_outcome == Booking.RefundOutcome.NONE
    assert ReliabilityEvent.objects.get(user=rahul).kind == K.NO_SHOW


def test_disputed_no_show_waits_for_ops(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at + timedelta(hours=1))
    services.mark_no_show(b, ride.driver)
    services.dispute_no_show(b, rahul, "I was at gate 2")
    clock.advance(hours=30)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.status == S.CONFIRMED and b.no_show_case.status == NoShowCase.Status.DISPUTED
    services.finalise_no_show(b.no_show_case, upheld=False, note="Driver called the wrong number")
    assert not ReliabilityEvent.objects.filter(kind=K.NO_SHOW).exists()


def test_dispute_after_window_rejected(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at + timedelta(hours=1))
    services.mark_no_show(b, ride.driver)
    clock.advance(hours=24)
    with pytest.raises(Conflict):
        services.dispute_no_show(b, rahul)


def test_overdue_refund_is_open_dispute_then_resolves(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    services.cancel_by_passenger(b, rahul)
    clock.advance(hours=47, minutes=59)
    sweeps.run_all(clock.now)
    assert not ReliabilityEvent.objects.filter(kind=K.REFUND_OVERDUE).exists()
    clock.advance(minutes=1)  # due in 24 h, plus 24 h unconfirmed
    sweeps.run_all(clock.now)
    refresh_reliability_view()
    assert reliability_for(ride.driver)["open_refund_disputes"] == 1

    services.confirm_refund_received(b, rahul)
    refresh_reliability_view()
    assert reliability_for(ride.driver)["open_refund_disputes"] == 0


def test_reliability_events_are_append_only(ride, rahul, confirm):
    b = confirm(ride, rahul)
    services.cancel_by_passenger(b, rahul)
    event = ReliabilityEvent.objects.get()
    event.note = "edited"
    with pytest.raises(ValueError):
        event.save()
    with pytest.raises(ValueError):
        event.delete()


def test_public_record_counts(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=20))
    services.cancel_by_passenger(b, rahul)
    refresh_reliability_view()
    record = reliability_for(rahul)
    assert record["passenger_late_cancellations"] == 1
    assert record["completed_trips"] == 0
