"""Last-seat race. Needs PostgreSQL: SQLite ignores SELECT ... FOR UPDATE."""
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection, connections
from django.utils import timezone

from apps.accounts.models import User, Vehicle
from apps.bookings import services
from apps.bookings.models import Booking
from apps.core.errors import Conflict
from apps.core.models import CityPair, PolicyVersion
from apps.rides.models import Ride

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="row locking needs PostgreSQL"),
]


def _setup():
    now = timezone.now()
    policy = PolicyVersion.objects.create(label="race", effective_from=now - timedelta(days=1),
                                          fuel_cost_per_km=Decimal("7"), summary="x")
    pair = CityPair.objects.create(origin="Pune", destination="Wardha", distance_km=640, tolls_inr=1100)
    driver = User.objects.create_user("+919100000001", name="D", hometown="Pune", terms_accepted_at=now)
    car = Vehicle.objects.create(owner=driver, make_model="Car", registration="MH12AB1234", passenger_seats=4)
    dep = now + timedelta(days=4)
    ride = Ride.objects.create(driver=driver, vehicle=car, city_pair=pair, policy_version=policy, departure_at=dep,
                               original_departure_at=dep, expected_arrival_at=dep + timedelta(hours=11),
                               pickup_point="A", dropoff_point="B", seats_offered=1, suggested_fare_inr=1000,
                               fare_inr=1000, advance_inr=300)
    requests = []
    for i in range(4):
        p = User.objects.create_user(f"+91910000001{i}", name=f"P{i}", hometown="Wardha", terms_accepted_at=now)
        requests.append(Booking.objects.create(
            ride=ride, passenger=p, policy_version=policy, fare_inr=1000, advance_inr=300,
            passenger_policy_ack_at=now, request_expires_at=now + timedelta(hours=12),
        ))
    return ride, driver, requests


def test_only_one_accept_wins_the_last_seat():
    ride, driver, requests = _setup()
    barrier = threading.Barrier(len(requests))
    results = []

    def worker(b):
        try:
            barrier.wait()
            services.accept(b, driver)
            results.append("ok")
        except Conflict:
            results.append("full")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(b,)) for b in requests]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("ok") == 1
    assert ride.bookings.filter(status__in=Booking.HOLDING).count() == 1
