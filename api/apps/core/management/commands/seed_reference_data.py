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


class Command(BaseCommand):
    help = "Create the corridor city pairs, the first policy version and festival seasons. Safe to rerun."

    @transaction.atomic
    def handle(self, *args, **options):
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
        Season.objects.get_or_create(
            name="Diwali 2026",
            defaults={
                "starts_at": datetime(2026, 10, 30, tzinfo=IST),
                "ends_at": datetime(2026, 11, 16, tzinfo=IST),
            },
        )
        self.stdout.write(self.style.SUCCESS("Reference data ready."))
