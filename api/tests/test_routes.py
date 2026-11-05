"""Route network: leg sums, per-leg cost share with the 15% cap, route posting and optional advance."""
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.bookings import services
from apps.bookings.models import Booking, Payment
from apps.core import policy as calc
from apps.core.errors import DomainError
from apps.notifications.models import Notification
from apps.routes import services as routes
from apps.trust.models import ReliabilityEvent

S = Booking.Status


class TestSegments:
    def test_full_route_sums_every_leg(self, network):
        p = network["places"]
        seg = routes.segment(network["via_wardha"], p["Pune"], p["Chandrapur"])
        assert seg.distance_km == Decimal("800.0")
        assert seg.tolls_inr == 1400
        assert seg.minutes == 780
        assert [s.place.name for s in seg.stops] == ["Pune", "Wardha", "Chandrapur"]

    def test_partial_segment(self, network):
        p = network["places"]
        seg = routes.segment(network["via_wardha"], p["Wardha"], p["Chandrapur"])
        assert seg.distance_km == Decimal("160.0") and seg.tolls_inr == 300

    def test_from_must_come_before_to(self, network):
        p = network["places"]
        with pytest.raises(DomainError):
            routes.segment(network["via_wardha"], p["Chandrapur"], p["Pune"])

    def test_place_not_on_route(self, network):
        p = network["places"]
        with pytest.raises(DomainError):
            routes.segment(network["via_wardha"], p["Pune"], p["Yavatmal"])

    def test_unverified_leg_is_not_ready(self, network):
        p = network["places"]
        seg = routes.segment(network["via_yavatmal"], p["Pune"], p["Chandrapur"], require_ready=False)
        assert not seg.ready
        with pytest.raises(DomainError) as exc:
            routes.segment(network["via_yavatmal"], p["Pune"], p["Chandrapur"])
        assert exc.value.code == "route_not_ready"

    def test_demo_leg_rejected_outside_debug(self, network, settings):
        leg = network["legs"][("Pune", "Wardha")]
        leg.source = leg.Source.DEMO
        leg.save()
        p = network["places"]
        settings.DEBUG = False
        with pytest.raises(DomainError):
            routes.segment(network["via_wardha"], p["Pune"], p["Wardha"])
        settings.DEBUG = True
        assert routes.segment(network["via_wardha"], p["Pune"], p["Wardha"]).ready

    def test_via_label(self):
        assert routes.via_label(["Pune", "Chandrapur"]) == "Direct"
        assert routes.via_label(["Pune", "Wardha", "Chandrapur"]) == "via Wardha"
        assert routes.via_label(["Pune", "A", "B", "C"]) == "via A and B"
        assert routes.via_label(["Pune", "A", "B", "C", "D"]) == "via A, B and C"

    def test_identical_stretches_offered_once(self, network):
        from apps.routes.models import Route, RouteStop

        p = network["places"]
        twin = Route.objects.create(name="Pune to Wardha", slug="pune-wardha")
        RouteStop.objects.create(route=twin, place=p["Pune"], position=0)
        RouteStop.objects.create(route=twin, place=p["Wardha"], position=1)
        assert len(routes.routes_between(p["Pune"], p["Wardha"])) == 1

    def test_routes_between_respects_direction(self, network):
        p = network["places"]
        found = {r.route.slug for r in routes.routes_between(p["Pune"], p["Chandrapur"])}
        assert found == {"pune-chandrapur-wardha", "pune-chandrapur-yavatmal"}
        assert {r.route.slug for r in routes.routes_between(p["Pune"], p["Wardha"])} == {"pune-chandrapur-wardha"}
        assert routes.routes_between(p["Chandrapur"], p["Pune"]) == []


class TestPerLegFare:
    def test_cost_share_and_15_percent_cap(self, network, policy):
        p = network["places"]
        q = routes.quote(network["via_wardha"], p["Pune"], p["Chandrapur"], seats_offered=3, policy=policy)
        # (800 x 7 + 1400) / (3 + 1) = 1750, cap 15% above
        assert q["suggested_fare_inr"] == 1750
        assert q["max_fare_inr"] == 2012
        assert q["distance_km"] == "800.0" and q["tolls_inr"] == 1400

    def test_partial_trip_cost_share(self, network, policy):
        p = network["places"]
        q = routes.quote(network["via_wardha"], p["Pune"], p["Wardha"], seats_offered=3, policy=policy)
        assert q["suggested_fare_inr"] == 1395  # (640 x 7 + 1100) / 4
        q = routes.quote(network["via_wardha"], p["Wardha"], p["Chandrapur"], seats_offered=3, policy=policy)
        assert q["suggested_fare_inr"] == 355  # (160 x 7 + 300) / 4


class TestAdvancePercentOnly:
    @pytest.mark.parametrize("fare,expected", [
        (1750, 550),   # 525 -> nearest 50, half up
        (355, 100),    # 106.5 -> 100: no 300 floor any more
        (5000, 1500),  # no 1,000 ceiling any more
        (100, 50),     # rounds to 0, so one rounding unit
        (30, 30),      # never more than the fare
        (0, 0),
    ])
    def test_percentage_only(self, fare, expected):
        assert calc.advance_percent_only(fare, 30, 50) == expected


class TestRoutePosting:
    def test_snapshot_and_fields(self, post_route_ride, network, pair):
        ride = post_route_ride()
        assert ride.route == network["via_wardha"]
        assert ride.origin == "Pune" and ride.destination == "Chandrapur"
        assert ride.distance_km == Decimal("800.0") and ride.tolls_inr == 1400
        assert [s["name"] for s in ride.stops] == ["Pune", "Wardha", "Chandrapur"]
        assert ride.stops[1]["km"] == "640.0"
        assert ride.suggested_fare_inr == 1750
        assert ride.advance_required and ride.advance_inr == 550
        assert ride.pickup_point == "Shivajinagar bus stand"
        assert ride.expected_arrival_at == ride.departure_at + timedelta(minutes=780)

    def test_fare_above_cap_rejected(self, post_route_ride):
        with pytest.raises(DomainError) as exc:
            post_route_ride(fare_inr=2013)
        assert exc.value.code == "fare_above_cap"
        assert post_route_ride(fare_inr=2012).fare_inr == 2012

    def test_leg_correction_does_not_change_posted_ride(self, post_route_ride, network):
        ride = post_route_ride()
        leg = network["legs"][("Pune", "Wardha")]
        leg.distance_km = Decimal("700.0")
        leg.save()
        ride.refresh_from_db()
        assert ride.distance_km == Decimal("800.0") and ride.suggested_fare_inr == 1750

    def test_disabled_stop_recorded(self, post_route_ride, network):
        wardha = network["places"]["Wardha"]
        ride = post_route_ride(disabled_stop_ids=[wardha.pk])
        assert [s["enabled"] for s in ride.stops] == [True, False, True]

    def test_cannot_disable_start_or_end(self, post_route_ride, network):
        with pytest.raises(DomainError):
            post_route_ride(disabled_stop_ids=[network["places"]["Pune"].pk])

    def test_unready_route_rejected(self, post_route_ride, network):
        p = network["places"]
        with pytest.raises(DomainError):
            post_route_ride(route=network["via_yavatmal"], from_place=p["Pune"], to_place=p["Chandrapur"])

    def test_exact_pickup_details_stored(self, post_route_ride):
        ride = post_route_ride(pickup={"name": "Shivajinagar bus stand", "address": "Shivajinagar, Pune",
                                       "eloc": "ABC123"})
        assert ride.pickup_address == "Shivajinagar, Pune" and ride.pickup_eloc == "ABC123"

    def test_pickup_name_required(self, post_route_ride):
        with pytest.raises(DomainError):
            post_route_ride(pickup={"name": "  "})


class TestNoAdvanceRide:
    @pytest.fixture
    def free_ride(self, post_route_ride):
        return post_route_ride(advance_required=False)

    def test_ride_has_no_advance(self, free_ride):
        assert not free_ride.advance_required and free_ride.advance_inr == 0

    def test_accept_confirms_directly(self, free_ride, rahul):
        b = services.request_seat(free_ride, rahul, policy_ack=True)
        assert b.advance_inr == 0
        services.accept(b, free_ride.driver)
        b.refresh_from_db()
        assert b.status == S.CONFIRMED and b.confirmed_at and b.hold_expires_at is None
        assert not b.payments.exists()
        assert Notification.objects.filter(user=rahul, kind="still_coming_72").exists()

    def test_late_cancel_records_event_without_refund(self, free_ride, rahul, clock):
        b = services.request_seat(free_ride, rahul, policy_ack=True)
        services.accept(b, free_ride.driver)
        clock.set(free_ride.departure_at - timedelta(hours=20))
        services.cancel_by_passenger(b, rahul)
        b.refresh_from_db()
        assert b.status == S.CANCELLED_PASSENGER and not b.refund_outcome
        assert not b.payments.filter(kind=Payment.Kind.REFUND).exists()
        assert ReliabilityEvent.objects.get(user=rahul).kind == ReliabilityEvent.Kind.PASSENGER_LATE_CANCEL

    def test_driver_cancel_creates_no_refund(self, free_ride, rahul):
        b = services.request_seat(free_ride, rahul, policy_ack=True)
        services.accept(b, free_ride.driver)
        services.cancel_ride(free_ride, free_ride.driver)
        b.refresh_from_db()
        assert b.status == S.CANCELLED_DRIVER
        assert not Payment.objects.exists()

    def test_waitlist_offer_confirms_directly(self, post_route_ride, rahul, neha):
        ride = post_route_ride(advance_required=False, seats_offered=1, fare_inr=3000)
        b = services.request_seat(ride, rahul, policy_ack=True)
        services.accept(b, ride.driver)
        entry = services.join_waitlist(ride, neha)
        services.cancel_by_passenger(b, rahul)
        entry.refresh_from_db()
        nb = services.accept_waitlist_offer(entry, neha, policy_ack=True)
        assert nb.status == S.CONFIRMED and not nb.payments.exists()

    def test_cannot_claim_advance(self, free_ride, rahul):
        from apps.core.errors import Conflict

        b = services.request_seat(free_ride, rahul, policy_ack=True)
        with pytest.raises(Conflict):
            services.claim_advance(b, rahul)
