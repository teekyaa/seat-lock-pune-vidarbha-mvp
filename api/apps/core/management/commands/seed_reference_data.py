from datetime import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import CityPair, PolicyVersion, Season
from apps.core.timefmt import IST

# PLACEHOLDER figures. Distance, tolls and fuel cost are an open question in CLAUDE.md
# (source and upkeep). Replace with approved values in Django admin before launch.
CITY_PAIRS = [
    ("Pune", "Nagpur", 710, 1250, 12),
    ("Pune", "Wardha", 640, 1100, 11),
    ("Pune", "Chandrapur", 760, 1150, 13),
]

POLICY_SUMMARY = (
    "Your advance is 30% of the seat fare, between Rs 300 and Rs 1,000, paid straight to the driver over UPI. "
    "Your seat is confirmed when the driver marks the advance received. "
    "Cancel more than 48 hours before departure for a full refund. "
    "From 48 hours to 12 hours before, the driver keeps half. Under 12 hours, or if you don't turn up, the driver keeps all of it. "
    "If your seat is refilled before departure you get it all back. "
    "If the driver cancels, you get it all back within 24 hours."
)

POLICY_SUMMARY_V2 = (
    "If the driver asks for an advance, it is 30% of the seat fare, paid straight to the driver over UPI, "
    "and your seat is confirmed when the driver marks it received. "
    "Cancel more than 48 hours before departure for a full refund. "
    "From 48 hours to 12 hours before, the driver keeps half. Under 12 hours, or if you don't turn up, the driver keeps all of it. "
    "If your seat is refilled before departure you get it all back. "
    "If the driver cancels, you get it all back within 24 hours. "
    "Rides without an advance are confirmed when the driver accepts; late cancellations still show on your record."
)


# Route network (docs/ROUTE_NETWORK_SPEC.md). Coordinates are town centres, used to bias place search
# and to measure legs. The stop lists are a DRAFT pending the team's route choice (spec Q3).
# Leg distances and tolls are deliberately left empty: they are measured in admin and checked by a person (D3, D4).
PLACES = [
    # name, region, lat, lng, aliases
    ("Pune", "west", "18.520430", "73.856743", ""),
    ("Ahilyanagar", "west", "19.094800", "74.748000", "Ahmednagar"),
    ("Chhatrapati Sambhajinagar", "marathwada", "19.876200", "75.343300", "Aurangabad"),
    ("Jalna", "marathwada", "19.841000", "75.886400", ""),
    ("Akola", "vidarbha", "20.700200", "77.008200", ""),
    ("Amravati", "vidarbha", "20.937400", "77.779600", ""),
    ("Wardha", "vidarbha", "20.745300", "78.602200", ""),
    ("Nagpur", "vidarbha", "21.145800", "79.088200", ""),
    ("Yavatmal", "vidarbha", "20.388800", "78.120400", ""),
    ("Wani", "vidarbha", "20.056000", "78.953000", ""),
    ("Chandrapur", "vidarbha", "19.961500", "79.296100", ""),
]
WEST = ["Pune", "Ahilyanagar", "Chhatrapati Sambhajinagar", "Jalna"]
ROUTES = [
    # slug, name, stops (outbound). The return route is created automatically.
    ("pune-nagpur-samruddhi-wardha", "Pune to Nagpur via Samruddhi and Wardha", WEST + ["Wardha", "Nagpur"]),
    ("pune-nagpur-akola-amravati", "Pune to Nagpur via Akola and Amravati", WEST + ["Akola", "Amravati", "Nagpur"]),
    ("pune-chandrapur-samruddhi-wardha", "Pune to Chandrapur via Samruddhi and Wardha", WEST + ["Wardha", "Chandrapur"]),
    ("pune-chandrapur-yavatmal", "Pune to Chandrapur via Yavatmal", WEST + ["Yavatmal", "Wani", "Chandrapur"]),
]


def seed_route_network():
    from apps.routes.models import Leg, Place, Route, RouteStop

    places = {}
    for name, region, lat, lng, aliases in PLACES:
        places[name], _ = Place.objects.get_or_create(
            name=name, defaults={"region": region, "lat": Decimal(lat), "lng": Decimal(lng), "aliases": aliases})
    for slug, name, stops in ROUTES:
        back_name = f"{stops[-1]} to {stops[0]} " + name.split(" ", 3)[3]
        for route_slug, route_name, ordered in ((slug, name, stops), (f"{slug}-return", back_name, stops[::-1])):
            route, created = Route.objects.get_or_create(slug=route_slug, defaults={"name": route_name})
            if created:
                for i, stop in enumerate(ordered):
                    RouteStop.objects.create(route=route, place=places[stop], position=i)
            for a, b in zip(ordered, ordered[1:]):
                Leg.objects.get_or_create(from_place=places[a], to_place=places[b])


class Command(BaseCommand):
    help = "Create corridor places and draft routes, city pairs, the first policy version and seasons. Safe to rerun."

    @transaction.atomic
    def handle(self, *args, **options):
        seed_route_network()
        for origin, dest, km, tolls, hours in CITY_PAIRS:
            for a, b in ((origin, dest), (dest, origin)):
                CityPair.objects.get_or_create(
                    origin=a, destination=b,
                    defaults={"distance_km": km, "tolls_inr": tolls, "typical_duration_hours": hours},
                )
        PolicyVersion.objects.get_or_create(
            label="2026-10-v1",
            defaults={
                "effective_from": datetime(2026, 10, 1, tzinfo=IST),
                "fuel_cost_per_km": Decimal("7.00"),
                "summary": POLICY_SUMMARY,
            },
        )
        # Spec D6: advance is a percentage with no floor or ceiling, and drivers may switch it off.
        PolicyVersion.objects.get_or_create(
            label="2026-11-v2",
            defaults={
                "effective_from": datetime(2026, 11, 4, tzinfo=IST),
                "fuel_cost_per_km": Decimal("7.00"),
                "advance_min_inr": 0,
                "advance_max_inr": 0,
                "summary": POLICY_SUMMARY_V2,
            },
        )
        Season.objects.get_or_create(
            name="Diwali 2026",
            defaults={
                "starts_at": datetime(2026, 10, 30, tzinfo=IST),
                "ends_at": datetime(2026, 11, 16, tzinfo=IST),
            },
        )
        self.stdout.write(self.style.SUCCESS("Reference data ready."))
