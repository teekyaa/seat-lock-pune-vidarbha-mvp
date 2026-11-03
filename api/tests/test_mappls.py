"""Mappls client: place search and one-time leg measurement. No real network calls."""
import io
import json
from decimal import Decimal
from urllib.error import HTTPError

import pytest
from django.core.cache import cache

from apps.routes import mappls
from apps.routes.models import Leg


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(payload, seen):
    def _open(request, timeout=None):
        seen.append(request.full_url)
        return FakeResponse(json.dumps(payload).encode())
    return _open


def test_unconfigured_means_unavailable(settings):
    settings.MAPPLS_API_KEY = ""
    assert not mappls.configured()
    with pytest.raises(mappls.MapplsUnavailable):
        mappls.autosuggest("Shivajinagar")


def test_autosuggest_parses_and_caches(settings, monkeypatch):
    settings.MAPPLS_API_KEY = "test-key"
    seen = []
    payload = {"suggestedLocations": [
        {"placeName": "Shivajinagar Bus Stand", "placeAddress": "Shivajinagar, Pune", "eLoc": "ABC123"},
        {"placeName": "", "eLoc": "SKIP01"},
    ]}
    monkeypatch.setattr(mappls, "urlopen", fake_urlopen(payload, seen))
    results = mappls.autosuggest("shivajinagar", near=(Decimal("18.52"), Decimal("73.85")))
    assert results == [{"name": "Shivajinagar Bus Stand", "address": "Shivajinagar, Pune", "eloc": "ABC123"}]
    assert "location=18.52%2C73.85" in seen[0]
    mappls.autosuggest("Shivajinagar ", near=(Decimal("18.52"), Decimal("73.85")))
    assert len(seen) == 1  # second call served from cache


def test_errors_never_include_the_key(settings, monkeypatch):
    settings.MAPPLS_API_KEY = "secret-key-123"

    def boom(request, timeout=None):
        raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(mappls, "urlopen", boom)
    with pytest.raises(mappls.MapplsUnavailable) as exc:
        mappls.autosuggest("Wardha")
    assert "secret-key-123" not in str(exc.value)


def test_route_distance(settings, monkeypatch):
    settings.MAPPLS_API_KEY = "test-key"
    seen = []
    monkeypatch.setattr(mappls, "urlopen", fake_urlopen({"routes": [{"distance": 640449.7, "duration": 35940}]}, seen))
    km, minutes = mappls.route_distance((Decimal("18.5204"), Decimal("73.8567")), (Decimal("20.7453"), Decimal("78.6022")))
    assert km == Decimal("640.4") and minutes == 599
    assert "73.8567,18.5204;78.6022,20.7453" in seen[0]


def test_measure_leg_marks_it_unverified(network, settings, monkeypatch):
    settings.MAPPLS_API_KEY = "test-key"
    monkeypatch.setattr(mappls, "urlopen", fake_urlopen({"routes": [{"distance": 641000, "duration": 36000}]}, []))
    leg = network["legs"][("Pune", "Wardha")]
    mappls.measure_leg(leg)
    leg.refresh_from_db()
    assert leg.distance_km == Decimal("641.0") and leg.typical_minutes == 600
    assert leg.source == Leg.Source.MAPPLS and leg.verified_at is None
