"""HTTP layer for the route network: places, via-route options, quotes, posting and place search."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.auth import issue_token

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def client_for(user=None):
    c = APIClient()
    if user:
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_token(user)}")
    return c


def test_places_listed(network):
    names = {p["name"] for p in client_for().get("/api/v1/places").data}
    assert {"Pune", "Wardha", "Chandrapur", "Yavatmal"} <= names


def test_route_options_show_readiness_and_stops(network):
    p = network["places"]
    data = client_for().get(f"/api/v1/routes?from={p['Pune'].pk}&to={p['Chandrapur'].pk}").data
    assert [r["name"] for r in data] == ["Pune to Chandrapur via Wardha", "Pune to Chandrapur via Yavatmal"]
    assert data[0]["ready"] is True and data[1]["ready"] is False
    assert [s["name"] for s in data[0]["stops"]] == ["Pune", "Wardha", "Chandrapur"]
    assert data[0]["distance_km"] == "800.0"
    assert data[0]["label"] == "via Wardha" and data[1]["label"] == "via Yavatmal"


def test_route_quote(network, policy):
    p = network["places"]
    url = f"/api/v1/route-quote?route={network['via_wardha'].pk}&from={p['Pune'].pk}&to={p['Wardha'].pk}&seats=3"
    q = client_for().get(url).data
    assert q["suggested_fare_inr"] == 1395 and q["max_fare_inr"] == 1604


def payload(network, car, clock, **extra):
    p = network["places"]
    body = {
        "route": network["via_wardha"].pk, "from_place": p["Pune"].pk, "to_place": p["Chandrapur"].pk,
        "vehicle": car.pk, "departure_at": (clock.now + timedelta(days=3)).isoformat(), "seats_offered": 3,
        "fare_inr": 1750, "pickup": {"name": "Shivajinagar bus stand", "address": "Shivajinagar, Pune", "eloc": "ABC123"},
        "dropoff_point": "Chandrapur bus stand", "disabled_stops": [], "policy_ack": True,
    }
    body.update(extra)
    return body


def test_post_route_ride_and_privacy(network, car, driver, rahul, policy, clock):
    r = client_for(driver).post("/api/v1/rides", payload(network, car, clock), format="json")
    assert r.status_code == 201, r.data
    assert r.data["route"]["name"] == "Pune to Chandrapur via Wardha"
    assert r.data["route"]["label"] == "via Wardha"
    assert [s["name"] for s in r.data["route"]["stops"]] == ["Pune", "Wardha", "Chandrapur"]
    assert r.data["advance_required"] is True and r.data["advance_inr"] == 550
    public = client_for(rahul).get(f"/api/v1/rides/{r.data['code']}").data
    assert public["pickup_point"] == "Shivajinagar bus stand"
    assert "Shivajinagar, Pune" not in str(public)  # full address only for confirmed travellers


def test_post_no_advance_ride(network, car, driver, policy, clock):
    r = client_for(driver).post("/api/v1/rides", payload(network, car, clock, advance_required=False), format="json")
    assert r.status_code == 201
    assert r.data["advance_required"] is False and r.data["advance_inr"] == 0


def test_post_rejects_fare_above_cap(network, car, driver, policy, clock):
    r = client_for(driver).post("/api/v1/rides", payload(network, car, clock, fare_inr=2013), format="json")
    assert r.status_code == 400 and r.data["code"] == "fare_above_cap"


def test_post_rejects_string_advance_flag(network, car, driver, policy, clock):
    r = client_for(driver).post("/api/v1/rides", payload(network, car, clock, advance_required="false"), format="json")
    assert r.status_code == 400


def test_search_by_place_names(network, car, driver, policy, clock):
    client_for(driver).post("/api/v1/rides", payload(network, car, clock), format="json")
    assert len(client_for().get("/api/v1/rides?origin=Pune&destination=Chandrapur").data) == 1
    assert len(client_for().get("/api/v1/rides?origin=Pune&destination=Nagpur").data) == 0


def test_place_search_falls_back_when_mappls_off(network, rahul, settings):
    settings.MAPPLS_API_KEY = ""
    r = client_for(rahul).get(f"/api/v1/places/search?q=shivaji&near={network['places']['Pune'].pk}")
    assert r.status_code == 200 and r.data == {"available": False, "results": []}


def test_place_search_needs_sign_in(network):
    assert client_for().get("/api/v1/places/search?q=shivaji").status_code in (401, 403)
