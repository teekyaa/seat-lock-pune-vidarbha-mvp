"""Route arithmetic: which routes connect two places, and what a stretch of a route costs."""
from dataclasses import dataclass, field
from decimal import Decimal

from apps.core import policy as calc
from apps.core.errors import DomainError
from apps.core.models import PolicyVersion

from .models import Leg, Place, Route


@dataclass
class Stop:
    place: Place
    km: Decimal = Decimal("0")       # cumulative from the segment start
    tolls: int = 0                   # cumulative from the segment start
    minutes: int = 0                 # cumulative from the segment start


@dataclass
class Segment:
    route: Route
    stops: list = field(default_factory=list)
    legs: list = field(default_factory=list)
    missing: list = field(default_factory=list)  # (from, to) pairs with no leg row

    @property
    def ready(self):
        return not self.missing and all(leg.ready() for leg in self.legs)

    @property
    def distance_km(self):
        return self.stops[-1].km

    @property
    def tolls_inr(self):
        return self.stops[-1].tolls

    @property
    def minutes(self):
        return self.stops[-1].minutes if all(leg.typical_minutes is not None for leg in self.legs) else None


def ordered_places(route):
    return [s.place for s in route.stops.select_related("place").order_by("position")]


def segment(route, from_place, to_place, *, require_ready=True):
    """The stretch of `route` from `from_place` to `to_place`, with cumulative distance and tolls."""
    places = ordered_places(route)
    ids = [p.pk for p in places]
    if from_place.pk not in ids or to_place.pk not in ids:
        raise DomainError("Both places need to be on the chosen route.", "place_not_on_route")
    start, end = ids.index(from_place.pk), ids.index(to_place.pk)
    if start >= end:
        raise DomainError(f"{from_place.name} comes after {to_place.name} on this route.", "wrong_direction")
    span = places[start:end + 1]
    legs = {(leg.from_place_id, leg.to_place_id): leg for leg in Leg.objects.filter(
        from_place_id__in=[p.pk for p in span[:-1]], to_place_id__in=[p.pk for p in span[1:]])}
    seg = Segment(route=route, stops=[Stop(place=span[0])])
    for a, b in zip(span, span[1:]):
        leg = legs.get((a.pk, b.pk))
        prev = seg.stops[-1]
        if leg is None:
            seg.missing.append((a, b))
            seg.stops.append(Stop(place=b, km=prev.km, tolls=prev.tolls, minutes=prev.minutes))
            continue
        seg.legs.append(leg)
        seg.stops.append(Stop(
            place=b,
            km=prev.km + (leg.distance_km or Decimal("0")),
            tolls=prev.tolls + (leg.tolls_inr or 0),
            minutes=prev.minutes + (leg.typical_minutes or 0),
        ))
    if require_ready and not seg.ready:
        raise DomainError("This route isn't open yet: some of its distances or tolls are still being checked.",
                          "route_not_ready")
    return seg


@dataclass
class RouteOption:
    route: Route
    segment: Segment


def routes_between(from_place, to_place):
    """Active routes that pass `from_place` and then `to_place`, ready ones first.
    Routes that share the exact same stops for this stretch are offered once."""
    options = []
    for route in Route.objects.filter(active=True, stops__place=from_place).filter(stops__place=to_place).distinct():
        try:
            options.append(RouteOption(route, segment(route, from_place, to_place, require_ready=False)))
        except DomainError:
            continue  # wrong direction on this route
    options.sort(key=lambda o: (not o.segment.ready, o.segment.distance_km, o.route.pk))
    seen, unique = set(), []
    for option in options:
        key = tuple(s.place.pk for s in option.segment.stops)
        if key not in seen:
            seen.add(key)
            unique.append(option)
    return unique


def via_label(stop_names):
    """'via Ahilyanagar, Jalna and Wardha' from a full stop list, or 'Direct'."""
    middle = list(stop_names[1:-1])
    if not middle:
        return "Direct"
    return "via " + (middle[0] if len(middle) == 1 else ", ".join(middle[:-1]) + " and " + middle[-1])


def cost_inr(seg, policy):
    return seg.distance_km * Decimal(str(policy.fuel_cost_per_km)) + seg.tolls_inr


def quote(route, from_place, to_place, seats_offered, policy=None):
    """Hard rule 2, per leg: cost share = (km x fuel + tolls) / (seats + 1), cap 15% above it."""
    policy = policy or PolicyVersion.current()
    seg = segment(route, from_place, to_place)
    suggested = calc.suggested_fare(seg.distance_km, seg.tolls_inr, seats_offered, policy.fuel_cost_per_km)
    return {
        "route_id": route.pk,
        "from_place_id": from_place.pk,
        "to_place_id": to_place.pk,
        "distance_km": str(seg.distance_km),
        "tolls_inr": seg.tolls_inr,
        "fuel_cost_per_km": str(policy.fuel_cost_per_km),
        "seats_offered": seats_offered,
        "suggested_fare_inr": suggested,
        "max_fare_inr": calc.max_fare(suggested, policy.fare_cap_percent),
        "advance_percent": policy.advance_percent,
        "advance_inr": calc.advance_percent_only(suggested, policy.advance_percent, policy.advance_round_to_inr),
        "policy_version": policy.label,
    }


def stop_json(stop):
    return {"place_id": stop.place.pk, "name": stop.place.name, "km": str(stop.km), "tolls": stop.tolls,
            "minutes": stop.minutes}


def option_json(option):
    seg = option.segment
    return {
        "id": option.route.pk,
        "name": option.route.name,
        "label": via_label([s.place.name for s in seg.stops]),
        "distance_km": str(seg.distance_km),
        "tolls_inr": seg.tolls_inr,
        "minutes": seg.minutes,
        "ready": seg.ready,
        "stops": [stop_json(s) for s in seg.stops],
    }
