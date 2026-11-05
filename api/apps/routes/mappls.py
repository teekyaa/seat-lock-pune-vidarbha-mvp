"""Mappls (MapmyIndia) client. Server-side only: the key never reaches the browser.

- autosuggest(): dropdown search for an exact pickup point, biased to a town.
- route_distance() / measure_leg(): one-time measurement of a leg in Django admin. Never per search.

Endpoints follow the current Mappls REST docs and are configurable in settings.
"""
import json
from decimal import ROUND_HALF_UP, Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

AUTOSUGGEST_CACHE_SECONDS = 24 * 3600
MAX_RESULTS = 8


class MapplsUnavailable(Exception):
    """Mappls isn't configured or didn't answer. Callers fall back to free text or manual entry."""


def configured():
    return bool(settings.MAPPLS_API_KEY)


def _get_json(url):
    request = Request(url, headers={"User-Agent": "SeatLock/0.1", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=settings.MAPPLS_TIMEOUT_SECONDS) as response:
            if response.status != 200:
                raise MapplsUnavailable(f"Mappls returned HTTP {response.status}.")
            return json.load(response)
    except HTTPError as exc:
        # Never echo the URL: it carries the key.
        raise MapplsUnavailable(f"Mappls rejected the request (HTTP {exc.code}).") from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise MapplsUnavailable("Mappls could not be reached or returned an invalid response.") from None


def autosuggest(query, near=None):
    """Up to 8 places matching `query`, biased to `near` = (lat, lng). Results are cached for a day."""
    if not configured():
        raise MapplsUnavailable("Mappls is not configured.")
    query = " ".join(str(query).split())[:80]
    if len(query) < 2:
        return []
    bias = f"{near[0]},{near[1]}" if near else ""
    key = f"mappls:suggest:{query.lower()}:{bias}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    params = {"query": query, "access_token": settings.MAPPLS_API_KEY}
    if bias:
        params["location"] = bias
    data = _get_json(f"{settings.MAPPLS_AUTOSUGGEST_URL}?{urlencode(params)}")
    results = []
    for item in (data.get("suggestedLocations") or []) if isinstance(data, dict) else []:
        name = str(item.get("placeName") or "").strip()
        if not name:
            continue
        results.append({
            "name": name[:160],
            "address": str(item.get("placeAddress") or "").strip()[:300],
            "eloc": str(item.get("eLoc") or "").strip()[:12],
        })
        if len(results) == MAX_RESULTS:
            break
    cache.set(key, results, AUTOSUGGEST_CACHE_SECONDS)
    return results


def route_distance(start, end):
    """Driving distance and time between (lat, lng) points: (km to 0.1, minutes)."""
    if not configured():
        raise MapplsUnavailable("Mappls is not configured.")
    coords = f"{start[1]},{start[0]};{end[1]},{end[0]}"  # Mappls wants lng,lat
    url = settings.MAPPLS_ROUTE_URL.format(key=quote(settings.MAPPLS_API_KEY, safe=""), coords=coords)
    data = _get_json(url)
    try:
        route = data["routes"][0]
        metres, seconds = Decimal(str(route["distance"])), Decimal(str(route["duration"]))
    except (KeyError, IndexError, TypeError, ValueError, ArithmeticError):
        raise MapplsUnavailable("Mappls returned no route for these places.") from None
    km = (metres / 1000).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    minutes = int((seconds / 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return km, minutes


def measure_leg(leg):
    """Store a Mappls measurement on a leg and clear its verification: a person must check it."""
    km, minutes = route_distance((leg.from_place.lat, leg.from_place.lng), (leg.to_place.lat, leg.to_place.lng))
    leg.distance_km = km
    leg.typical_minutes = minutes
    leg.source = leg.Source.MAPPLS
    leg.verified_at = None
    leg.verified_by = None
    leg.save()
    return leg
