from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import User, Vehicle
from apps.bookings import services
from apps.core.models import CityPair, PolicyVersion, Season
from apps.rides.models import Ride

START = datetime(2026, 9, 1, 6, 0, tzinfo=dt_timezone.utc)  # outside the Diwali season


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, **kwargs):
        self.now = self.now + timedelta(**kwargs)
        return self.now

    def set(self, moment):
        self.now = moment
        return self.now


@pytest.fixture(autouse=True)
def _isolate_settings(settings, monkeypatch):
    # Tests never send SMS or depend on a developer's api/.env.
    settings.OTP_DEBUG_ECHO = False
    settings.TEXTBEE_API_KEY = ""
    settings.TEXTBEE_DEVICE_ID = ""
    settings.OTP_TRUSTED_PROXY_IPS = []
    fake_sms = SimpleNamespace(channel="sms", verifies_code=False, send_otp=lambda phone, code: None)
    monkeypatch.setattr("apps.accounts.otp.configured_backends", lambda: [("tests.fake.SMS", fake_sms)])


@pytest.fixture
def clock(monkeypatch):
    c = Clock(START)
    monkeypatch.setattr(timezone, "now", c)
    return c


@pytest.fixture
def policy(db, clock):
    return PolicyVersion.objects.create(
        label="test-v1", effective_from=START - timedelta(days=30), fuel_cost_per_km=Decimal("7.00"),
        summary="Test policy",
    )


@pytest.fixture
def pair(db):
    return CityPair.objects.create(origin="Pune", destination="Nagpur", distance_km=710, tolls_inr=1250,
                                   typical_duration_hours=12)


def make_user(phone, name, **extra):
    defaults = {"name": name, "hometown": "Wardha", "terms_accepted_at": START, "upi_id": f"{name.split()[0].lower()}@okaxis"}
    defaults.update(extra)
    return User.objects.create_user(phone, **defaults)


@pytest.fixture
def driver(db):
    return make_user("+919000000001", "Aditi Deshmukh", hometown="Nagpur", gender="female")


@pytest.fixture
def car(driver):
    return Vehicle.objects.create(owner=driver, make_model="Hyundai i20", colour="Blue", registration="MH31AB1234",
                                  passenger_seats=4)


@pytest.fixture
def rahul(db):
    return make_user("+919000000002", "Rahul Patil")


@pytest.fixture
def neha(db):
    return make_user("+919000000003", "Neha Kulkarni", gender="female")


@pytest.fixture
def sam(db):
    return make_user("+919000000004", "Sameer Joshi")


@pytest.fixture
def make_ride(driver, car, pair, policy, clock):
    def _make(hours_ahead=100, seats=2, fare=1500, **extra):
        dep = clock.now + timedelta(hours=hours_ahead)
        return Ride.objects.create(
            driver=driver, vehicle=car, city_pair=pair, policy_version=policy, departure_at=dep,
            original_departure_at=dep, expected_arrival_at=dep + timedelta(hours=12), pickup_point="Shivajinagar",
            dropoff_point="Nagpur station", pickup_details="Gate 2", seats_offered=seats, suggested_fare_inr=1555,
            fare_inr=fare, advance_inr=450, **extra,
        )
    return _make


@pytest.fixture
def ride(make_ride):
    return make_ride()


@pytest.fixture
def confirm():
    """Walk a passenger all the way to a confirmed seat."""
    def _confirm(ride, passenger):
        b = services.request_seat(ride, passenger, policy_ack=True)
        services.accept(b, ride.driver)
        services.claim_advance(b, passenger)
        services.confirm_advance(b, ride.driver)
        b.refresh_from_db()
        return b
    return _confirm


@pytest.fixture
def network(db, driver):
    """Pune to Chandrapur via Wardha, verified legs. Figures are test fixtures, not real data."""
    from apps.routes.models import Leg, Place, Route, RouteStop

    places = {
        name: Place.objects.create(name=name, region=region, lat=lat, lng=lng)
        for name, region, lat, lng in [
            ("Pune", "west", Decimal("18.5204"), Decimal("73.8567")),
            ("Wardha", "vidarbha", Decimal("20.7453"), Decimal("78.6022")),
            ("Chandrapur", "vidarbha", Decimal("19.9615"), Decimal("79.2961")),
            ("Yavatmal", "vidarbha", Decimal("20.3888"), Decimal("78.1204")),
        ]
    }
    verified = {"source": Leg.Source.MANUAL, "verified_at": START, "verified_by": driver}
    legs = {
        ("Pune", "Wardha"): Leg.objects.create(from_place=places["Pune"], to_place=places["Wardha"],
                                               distance_km=Decimal("640.0"), tolls_inr=1100, typical_minutes=600, **verified),
        ("Wardha", "Chandrapur"): Leg.objects.create(from_place=places["Wardha"], to_place=places["Chandrapur"],
                                                     distance_km=Decimal("160.0"), tolls_inr=300, typical_minutes=180, **verified),
        ("Pune", "Yavatmal"): Leg.objects.create(from_place=places["Pune"], to_place=places["Yavatmal"],
                                                 distance_km=Decimal("620.0"), tolls_inr=1000, typical_minutes=620, **verified),
        ("Yavatmal", "Chandrapur"): Leg.objects.create(from_place=places["Yavatmal"], to_place=places["Chandrapur"],
                                                       distance_km=Decimal("170.0"), tolls_inr=150, typical_minutes=200),
    }
    via_wardha = Route.objects.create(name="Pune to Chandrapur via Wardha", slug="pune-chandrapur-wardha")
    via_yavatmal = Route.objects.create(name="Pune to Chandrapur via Yavatmal", slug="pune-chandrapur-yavatmal")
    for route, names in ((via_wardha, ["Pune", "Wardha", "Chandrapur"]), (via_yavatmal, ["Pune", "Yavatmal", "Chandrapur"])):
        for i, name in enumerate(names):
            RouteStop.objects.create(route=route, place=places[name], position=i)
    return {"places": places, "legs": legs, "via_wardha": via_wardha, "via_yavatmal": via_yavatmal}


@pytest.fixture
def post_route_ride(driver, car, network, policy, clock):
    """Post a ride on the verified via-Wardha route through the real service."""
    from apps.rides.services import create_route_ride

    def _post(**overrides):
        p = network["places"]
        args = dict(
            route=network["via_wardha"], from_place=p["Pune"], to_place=p["Chandrapur"], vehicle=car,
            departure_at=clock.now + timedelta(days=4), seats_offered=3, fare_inr=1750,
            pickup={"name": "Shivajinagar bus stand"}, dropoff_point="Chandrapur bus stand", policy_ack=True,
        )
        args.update(overrides)
        return create_route_ride(driver, **args)
    return _post


@pytest.fixture
def diwali(db):
    return Season.objects.create(name="Diwali", starts_at=START - timedelta(days=1), ends_at=START + timedelta(days=20))
