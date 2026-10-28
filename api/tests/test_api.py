"""HTTP layer: OTP sign-in, contact privacy, and the booking actions end to end."""
import re
from datetime import timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.auth import issue_token
from apps.accounts.models import OTPChallenge

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def client_for(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_token(user)}")
    return c


@pytest.fixture
def otp(settings):
    settings.OTP_DEBUG_ECHO = True


def test_otp_sign_in_creates_user(otp, policy):
    c = APIClient()
    r = c.post("/api/v1/auth/otp/request", {"phone": "98765 43210"}, format="json")
    assert r.status_code == 200 and r.data["phone"] == "+919876543210"
    code = r.data["debug_code"]
    assert not OTPChallenge.objects.filter(code_hash=code).exists()  # only the hash is stored
    r = c.post("/api/v1/auth/otp/verify", {"phone": "9876543210", "code": code}, format="json")
    assert r.status_code == 200 and r.data["is_new"] is True
    me = APIClient()
    me.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['token']}")
    assert me.get("/api/v1/me").data["phone"] == "+919876543210"
    # The code works only once
    r = c.post("/api/v1/auth/otp/verify", {"phone": "9876543210", "code": code}, format="json")
    assert r.status_code == 400


def test_otp_wrong_code_locks_after_five(otp, policy):
    c = APIClient()
    code = c.post("/api/v1/auth/otp/request", {"phone": "9876543210"}, format="json").data["debug_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        r = c.post("/api/v1/auth/otp/verify", {"phone": "9876543210", "code": wrong}, format="json")
        assert r.status_code == 400
    r = c.post("/api/v1/auth/otp/verify", {"phone": "9876543210", "code": code}, format="json")
    assert r.data["code"] == "otp_locked"


def test_otp_send_rate_limited(otp, policy):
    c = APIClient()
    for _ in range(3):
        assert c.post("/api/v1/auth/otp/request", {"phone": "9876543210"}, format="json").status_code == 200
    assert c.post("/api/v1/auth/otp/request", {"phone": "9876543210"}, format="json").status_code == 429


def test_otp_expires(otp, policy, clock):
    c = APIClient()
    code = c.post("/api/v1/auth/otp/request", {"phone": "9876543210"}, format="json").data["debug_code"]
    clock.advance(minutes=6)
    r = c.post("/api/v1/auth/otp/verify", {"phone": "9876543210", "code": code}, format="json")
    assert r.data["code"] == "otp_expired"


def test_no_debug_code_unless_enabled(policy):
    r = APIClient().post("/api/v1/auth/otp/request", {"phone": "9876543210"}, format="json")
    assert "debug_code" not in r.data


def test_invalid_phone_rejected(policy):
    r = APIClient().post("/api/v1/auth/otp/request", {"phone": "12345"}, format="json")
    assert r.status_code == 400


def test_public_ride_hides_contact(ride):
    r = client_for().get(f"/api/v1/rides/{ride.code}")
    assert r.status_code == 200
    body = str(r.data)
    assert "private" not in r.data
    assert ride.driver.phone not in body and "MH31AB1234" not in body and "Gate 2" not in body
    assert ride.driver.upi_id not in body


def test_full_booking_flow_over_http(ride, rahul):
    driver = client_for(ride.driver)
    passenger = client_for(rahul)
    r = passenger.post(f"/api/v1/rides/{ride.code}/request", {"note": "Hi", "policy_ack": True}, format="json")
    assert r.status_code == 201, r.data
    code = r.data["code"]
    assert "pay" not in r.data and "contact" not in r.data

    r = driver.post(f"/api/v1/bookings/{code}/accept")
    assert r.data["status"] == "accepted"
    assert "contact" not in r.data

    r = passenger.get(f"/api/v1/bookings/{code}")
    assert r.data["pay"]["upi_link"].startswith("upi://pay?pa=aditi@okaxis&")
    assert f"tn={code}" in r.data["pay"]["upi_link"]
    assert "contact" not in r.data  # phone and registration still hidden

    passenger.post(f"/api/v1/bookings/{code}/claim-advance", {"utr": "123456789012"}, format="json")
    r = driver.post(f"/api/v1/bookings/{code}/confirm-advance")
    assert r.data["status"] == "confirmed"
    assert r.data["contact"]["phone"] == rahul.phone

    r = passenger.get(f"/api/v1/bookings/{code}")
    assert r.data["contact"]["registration"] == "MH31AB1234"
    assert "IST" in r.data["cutoffs"]["full_refund_until"]["ist"]
    assert "cancel" in r.data["actions"]

    r = passenger.get(f"/api/v1/rides/{ride.code}")
    assert r.data["private"]["driver_phone"] == ride.driver.phone

    r = passenger.post(f"/api/v1/bookings/{code}/cancel")
    assert r.data["refund_outcome"] == "full"
    refund_link = driver.get(f"/api/v1/bookings/{code}").data["refund_pay"]["upi_link"]
    assert refund_link.startswith("upi://pay?pa=rahul@okaxis")


def test_other_users_cannot_see_booking(ride, rahul, neha):
    b = client_for(rahul).post(f"/api/v1/rides/{ride.code}/request", {"policy_ack": True}, format="json").data
    assert client_for(neha).get(f"/api/v1/bookings/{b['code']}").status_code == 403
    assert client_for(neha).post(f"/api/v1/bookings/{b['code']}/accept").status_code == 403


def test_post_ride_with_fare_cap(driver, car, pair, policy, clock):
    c = client_for(driver)
    quote = c.get(f"/api/v1/fare-quote?city_pair={pair.pk}&seats=3").data
    assert quote["suggested_fare_inr"] == 1555 and quote["max_fare_inr"] == 1788
    dep = (clock.now + timedelta(days=3)).isoformat()
    payload = {"city_pair": pair.pk, "vehicle": car.pk, "departure_at": dep, "seats_offered": 3,
               "fare_inr": 2000, "pickup_point": "Swargate", "dropoff_point": "Sitabuldi", "policy_ack": True}
    r = c.post("/api/v1/rides", payload, format="json")
    assert r.status_code == 400 and r.data["code"] == "fare_above_cap"
    payload["fare_inr"] = 1600
    r = c.post("/api/v1/rides", payload, format="json")
    assert r.status_code == 201
    assert re.fullmatch(r"[A-Z2-9]{6}", r.data["code"])
    assert r.data["advance_inr"] == 500


def test_naive_departure_rejected(driver, car, pair, policy):
    payload = {"city_pair": pair.pk, "vehicle": car.pk, "departure_at": "2026-11-06T21:00:00", "seats_offered": 2,
               "fare_inr": 1000, "pickup_point": "A", "dropoff_point": "B", "policy_ack": True}
    assert client_for(driver).post("/api/v1/rides", payload, format="json").status_code == 400


def test_search_filters_and_hides_blocked(ride, rahul):
    from apps.trust.models import Block

    assert len(client_for().get("/api/v1/rides?origin=Pune&destination=Nagpur").data) == 1
    assert len(client_for().get("/api/v1/rides?origin=Nagpur").data) == 0
    Block.objects.create(blocker=rahul, blocked=ride.driver)
    assert len(client_for(rahul).get("/api/v1/rides").data) == 0


def test_inbox_shows_sent_notifications(ride, rahul, confirm, clock):
    from apps.notifications.tasks import run_tick

    confirm(ride, rahul)
    run_tick(clock.now)
    r = client_for(rahul).get("/api/v1/me/notifications")
    assert r.data["unread"] >= 1
    assert any(i["title"] == "Seat confirmed" for i in r.data["items"])


def test_unauthenticated_writes_rejected(ride):
    assert client_for().post(f"/api/v1/rides/{ride.code}/request").status_code in (401, 403)


def test_profile_completion(rahul):
    c = client_for(rahul)
    r = c.patch("/api/v1/me", {"upi_id": "not a upi"}, format="json")
    assert r.status_code == 400
    r = c.patch("/api/v1/me", {"upi_id": "rahul@oksbi", "accept_terms": True}, format="json")
    assert r.status_code == 200 and r.data["profile_complete"]
