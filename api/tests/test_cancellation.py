"""Passenger and driver cancellation tiers, refills, reschedules and season strikes."""
from datetime import timedelta

import pytest

from apps.accounts.models import Vehicle
from apps.bookings import services, sweeps
from apps.bookings.models import Booking, Payment
from apps.core.errors import Forbidden
from apps.rides.services import create_ride
from apps.trust.models import ReliabilityEvent

S = Booking.Status
O = Booking.RefundOutcome
K = ReliabilityEvent.Kind


def refund(booking):
    return booking.payments.filter(kind=Payment.Kind.REFUND).first()


def test_more_than_48h_full_refund_due_in_24h(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)  # departure is 100 h away
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.status == S.CANCELLED_PASSENGER
    assert b.refund_outcome == O.FULL and b.refund_inr == 450
    r = refund(b)
    assert r.status == Payment.Status.DUE and r.amount_inr == 450
    assert r.due_at == clock.now + timedelta(hours=24)
    assert ReliabilityEvent.objects.get(user=rahul).kind == K.PASSENGER_EARLY_CANCEL


def test_exactly_48h_is_half_tier(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=48))
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.refund_outcome == O.PENDING_REFILL and b.penalty_tier == "half"


def test_half_tier_settles_at_departure(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=30))
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.refund_outcome == O.PENDING_REFILL
    assert refund(b) is None  # decided at departure or refill, whichever first
    assert ReliabilityEvent.objects.get(user=rahul).kind == K.PASSENGER_LATE_CANCEL

    clock.set(ride.departure_at)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.refund_outcome == O.HALF and b.refund_inr == 225
    assert refund(b).amount_inr == 225


def test_under_12h_driver_keeps_all(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=11, minutes=59))
    services.cancel_by_passenger(b, rahul)
    clock.set(ride.departure_at + timedelta(minutes=1))
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.refund_outcome == O.NONE and b.refund_inr == 0
    assert refund(b) is None


def test_refill_gives_full_refund_any_timing(make_ride, rahul, neha, confirm, clock):
    ride = make_ride(seats=1)
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=20))
    services.cancel_by_passenger(b, rahul)
    replacement = services.request_seat(ride, neha, policy_ack=True)
    services.accept(replacement, ride.driver)
    services.confirm_advance(replacement, ride.driver)
    b.refresh_from_db()
    assert b.refund_outcome == O.FULL and b.refund_inr == 450
    assert b.refilled_by_id == replacement.pk
    assert refund(b).amount_inr == 450
    # Settling at departure must not change a refilled outcome
    clock.set(ride.departure_at)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.refund_outcome == O.FULL


def test_two_late_cancels_need_two_refills(make_ride, rahul, neha, sam, confirm, clock):
    ride = make_ride(seats=3)
    a = confirm(ride, rahul)
    b = confirm(ride, neha)
    clock.set(ride.departure_at - timedelta(hours=20))
    services.cancel_by_passenger(a, rahul)  # 2 confirmed at cancel
    services.cancel_by_passenger(b, neha)   # 1 confirmed at cancel
    c = services.request_seat(ride, sam, policy_ack=True)
    services.accept(c, ride.driver)
    services.confirm_advance(c, ride.driver)  # back to 1 confirmed
    a.refresh_from_db()
    b.refresh_from_db()
    # Only Neha's seat is back to its level at cancellation; Rahul's needs a second refill.
    assert b.refund_outcome == O.FULL
    assert a.refund_outcome == O.PENDING_REFILL


def test_cancel_before_confirmation_has_no_penalty(ride, rahul):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(b, ride.driver)
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.status == S.CANCELLED_PASSENGER and not b.refund_outcome
    assert not ReliabilityEvent.objects.exists()  # only confirmed bookings create events


def test_cancel_after_claim_refunds_in_full(ride, rahul):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(b, ride.driver)
    services.claim_advance(b, rahul)
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.refund_outcome == O.FULL
    assert refund(b).amount_inr == 450


def test_driver_cancel_refunds_everyone(ride, rahul, neha, confirm, clock):
    a = confirm(ride, rahul)
    b = services.request_seat(ride, neha, policy_ack=True)
    services.accept(b, ride.driver)
    services.claim_advance(b, neha)
    services.cancel_ride(ride, ride.driver)
    a.refresh_from_db()
    b.refresh_from_db()
    for booking in (a, b):
        assert booking.status == S.CANCELLED_DRIVER
        assert refund(booking).amount_inr == 450
        assert refund(booking).due_at == clock.now + timedelta(hours=24)
    assert ReliabilityEvent.objects.get(user=ride.driver).kind == K.DRIVER_EARLY_CANCEL


def test_driver_cancel_under_48h_is_late(ride, rahul, confirm, clock):
    confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=47))
    services.cancel_ride(ride, ride.driver)
    assert ReliabilityEvent.objects.get(user=ride.driver).kind == K.DRIVER_LATE_CANCEL


def test_driver_cancel_refunds_late_passenger_canceller(make_ride, rahul, confirm, clock):
    ride = make_ride()
    b = confirm(ride, rahul)
    clock.set(ride.departure_at - timedelta(hours=20))
    services.cancel_by_passenger(b, rahul)
    services.cancel_ride(ride, ride.driver)
    b.refresh_from_db()
    assert b.refund_outcome == O.FULL and refund(b).amount_inr == 450


def test_second_late_cancel_in_season_blocks_posting(make_ride, rahul, neha, confirm, clock, diwali, pair):
    for passenger in (rahul, neha):
        ride = make_ride(hours_ahead=30)
        confirm(ride, passenger)
        services.cancel_ride(ride, ride.driver)
    car = Vehicle.objects.get(owner=ride.driver)
    with pytest.raises(Forbidden) as exc:
        create_ride(ride.driver, city_pair=pair, vehicle=car, departure_at=clock.now + timedelta(days=2),
                    seats_offered=2, fare_inr=1500, pickup_point="A", dropoff_point="B", policy_ack=True)
    assert exc.value.code == "posting_blocked"
    clock.set(diwali.ends_at + timedelta(minutes=1))  # block lifts when the season ends
    create_ride(ride.driver, city_pair=pair, vehicle=car, departure_at=clock.now + timedelta(days=2),
                seats_offered=2, fare_inr=1500, pickup_point="A", dropoff_point="B", policy_ack=True)


def test_cancel_with_nobody_confirmed_has_no_event(ride, rahul):
    services.request_seat(ride, rahul, policy_ack=True)
    services.cancel_ride(ride, ride.driver)
    assert not ReliabilityEvent.objects.exists()


def test_big_reschedule_allows_free_cancel(ride, rahul, confirm, clock):
    b = confirm(ride, rahul)
    services.reschedule(ride, ride.driver, ride.departure_at + timedelta(hours=3))
    b.refresh_from_db()
    assert b.free_cancel_any_time
    assert ReliabilityEvent.objects.get(user=ride.driver).kind == K.DRIVER_CHANGE
    ride.refresh_from_db()
    clock.set(ride.departure_at - timedelta(hours=2))  # would normally be "driver keeps all"
    services.cancel_by_passenger(b, rahul)
    b.refresh_from_db()
    assert b.refund_outcome == O.FULL


def test_small_reschedule_keeps_tiers(ride, rahul, confirm):
    b = confirm(ride, rahul)
    services.reschedule(ride, ride.driver, ride.departure_at + timedelta(hours=2))
    b.refresh_from_db()
    assert not b.free_cancel_any_time
    assert not ReliabilityEvent.objects.exists()


def test_fare_above_cap_rejected(driver, car, pair, policy, clock):
    from apps.core.errors import DomainError

    with pytest.raises(DomainError) as exc:
        create_ride(driver, city_pair=pair, vehicle=car, departure_at=clock.now + timedelta(days=3),
                    seats_offered=3, fare_inr=1789, pickup_point="A", dropoff_point="B", policy_ack=True)
    assert exc.value.code == "fare_above_cap"
    ride = create_ride(driver, city_pair=pair, vehicle=car, departure_at=clock.now + timedelta(days=3),
                       seats_offered=3, fare_inr=1788, pickup_point="A", dropoff_point="B", policy_ack=True)
    assert ride.suggested_fare_inr == 1555
    assert ride.advance_inr == 550  # 30% of 1788 = 536.4 -> 550


def test_posting_needs_6h_lead(driver, car, pair, policy, clock):
    from apps.core.errors import DomainError

    with pytest.raises(DomainError):
        create_ride(driver, city_pair=pair, vehicle=car, departure_at=clock.now + timedelta(hours=5),
                    seats_offered=2, fare_inr=1500, pickup_point="A", dropoff_point="B", policy_ack=True)
