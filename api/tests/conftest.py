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
    monkeypatch.setattr("apps.accounts.api.sms_backend", lambda: SimpleNamespace(send_otp=lambda phone, code: None))


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
def diwali(db):
    return Season.objects.create(name="Diwali", starts_at=START - timedelta(days=1), ends_at=START + timedelta(days=20))
