"""Status flow: requested -> accepted -> advance_claimed -> confirmed, and the early exits."""
from datetime import timedelta

import pytest

from apps.bookings import services, sweeps
from apps.bookings.models import Booking, Payment
from apps.core.errors import Conflict, DomainError, Forbidden
from apps.trust.models import Block, ReliabilityEvent

S = Booking.Status


def test_happy_path(ride, rahul, clock):
    b = services.request_seat(ride, rahul, note="Two bags", policy_ack=True)
    assert b.status == S.REQUESTED
    assert b.policy_version_id == ride.policy_version_id  # hard rule 5
    assert b.request_expires_at == clock.now + timedelta(hours=12)

    services.accept(b, ride.driver)
    b.refresh_from_db()
    assert b.status == S.ACCEPTED
    assert b.hold_expires_at == clock.now + timedelta(hours=2)

    services.claim_advance(b, rahul, utr="123456789012")
    b.refresh_from_db()
    assert b.status == S.ADVANCE_CLAIMED
    assert b.payments.get().status == Payment.Status.CLAIMED

    services.confirm_advance(b, ride.driver)
    b.refresh_from_db()
    assert b.status == S.CONFIRMED
    assert b.payments.get().status == Payment.Status.CONFIRMED
    assert not ReliabilityEvent.objects.exists()  # confirmation alone creates no reliability event


def test_policy_ack_required(ride, rahul):
    with pytest.raises(DomainError):
        services.request_seat(ride, rahul, policy_ack=False)


def test_incomplete_profile_cannot_request(ride, rahul):
    rahul.terms_accepted_at = None
    rahul.save()
    with pytest.raises(DomainError):
        services.request_seat(ride, rahul, policy_ack=True)


def test_cannot_request_own_ride(ride):
    with pytest.raises(DomainError):
        services.request_seat(ride, ride.driver, policy_ack=True)


def test_duplicate_request_rejected(ride, rahul):
    services.request_seat(ride, rahul, policy_ack=True)
    with pytest.raises(Conflict):
        services.request_seat(ride, rahul, policy_ack=True)


def test_requests_close_12h_before(make_ride, rahul):
    ride = make_ride(hours_ahead=11)
    with pytest.raises(DomainError):
        services.request_seat(ride, rahul, policy_ack=True)


def test_request_expiry_never_past_close(make_ride, rahul, clock):
    ride = make_ride(hours_ahead=20)
    b = services.request_seat(ride, rahul, policy_ack=True)
    assert b.request_expires_at == ride.departure_at - timedelta(hours=12)


def test_only_driver_accepts(ride, rahul, neha):
    b = services.request_seat(ride, rahul, policy_ack=True)
    with pytest.raises(Forbidden):
        services.accept(b, neha)


def test_decline(ride, rahul):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.decline(b, ride.driver)
    b.refresh_from_db()
    assert b.status == S.DECLINED
    with pytest.raises(Conflict):
        services.accept(b, ride.driver)


def test_request_expires_via_sweep(ride, rahul, clock):
    b = services.request_seat(ride, rahul, policy_ack=True)
    clock.advance(hours=12)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.status == S.EXPIRED


def test_accept_after_expiry_fails(ride, rahul, clock):
    b = services.request_seat(ride, rahul, policy_ack=True)
    clock.advance(hours=13)
    with pytest.raises(Conflict):
        services.accept(b, ride.driver)
    b.refresh_from_db()
    assert b.status == S.EXPIRED


def test_unpaid_hold_expires_after_2h(ride, rahul, clock):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(b, ride.driver)
    clock.advance(hours=2)
    with pytest.raises(Conflict):
        services.claim_advance(b, rahul)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.status == S.HOLD_EXPIRED


def test_claimed_advance_does_not_expire(ride, rahul, clock):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(b, ride.driver)
    services.claim_advance(b, rahul)
    clock.advance(hours=5)
    sweeps.run_all(clock.now)
    b.refresh_from_db()
    assert b.status == S.ADVANCE_CLAIMED


def test_driver_can_confirm_without_passenger_claim(ride, rahul):
    b = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(b, ride.driver)
    services.confirm_advance(b, ride.driver)
    b.refresh_from_db()
    assert b.status == S.CONFIRMED
    assert b.payments.get().status == Payment.Status.CONFIRMED


def test_cannot_confirm_from_requested(ride, rahul):
    b = services.request_seat(ride, rahul, policy_ack=True)
    with pytest.raises(Conflict):
        services.confirm_advance(b, ride.driver)


def test_holds_reserve_seats(make_ride, rahul, neha, sam):
    ride = make_ride(seats=1)
    a = services.request_seat(ride, rahul, policy_ack=True)
    b = services.request_seat(ride, neha, policy_ack=True)
    services.accept(a, ride.driver)
    with pytest.raises(Conflict):
        services.accept(b, ride.driver)  # the only seat is held by an unpaid hold
    with pytest.raises(Conflict):
        services.request_seat(ride, sam, policy_ack=True)


def test_blocked_members_cannot_book(ride, rahul):
    Block.objects.create(blocker=ride.driver, blocked=rahul)
    with pytest.raises(Forbidden):
        services.request_seat(ride, rahul, policy_ack=True)


def test_women_only_requires_verified_passenger(make_ride, neha):
    ride = make_ride(women_only=True)
    with pytest.raises(Forbidden):
        services.request_seat(ride, neha, policy_ack=True)  # self-declared female, not verified
    neha.women_only_eligible = True
    neha.save()
    assert services.request_seat(ride, neha, policy_ack=True).status == S.REQUESTED


def test_policy_version_in_use_is_immutable(ride, rahul, policy):
    services.request_seat(ride, rahul, policy_ack=True)
    policy.advance_percent = 40
    with pytest.raises(ValueError):
        policy.save()


def test_upi_link_format():
    link = services.upi_link("aditi@okaxis", "Aditi Deshmukh", 450, "SLABC123")
    assert link == "upi://pay?pa=aditi@okaxis&pn=Aditi%20Deshmukh&am=450&cu=INR&tn=SLABC123"
