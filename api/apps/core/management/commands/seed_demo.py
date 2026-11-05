from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User, Vehicle
from apps.rides.models import Ride
from apps.rides.services import create_route_ride

# Synthetic people only. Sign in as any of them with the console OTP.
DEMO_USERS = [
    ("+919000010001", "Aditi Deshmukh", "Nagpur", "female", "aditi.demo@okaxis"),
    ("+919000010002", "Rahul Patil", "Wardha", "male", "rahul.demo@okhdfc"),
    ("+919000010003", "Neha Kulkarni", "Wardha", "female", "neha.demo@oksbi"),
]

# SYNTHETIC leg figures so the route flow can be tried locally. Marked source=demo, which the app
# refuses to price with outside DEBUG. Real figures are measured in admin and checked (spec D3, D4).
DEMO_LEGS = {
    ("Pune", "Ahilyanagar"): (120, 90), ("Ahilyanagar", "Chhatrapati Sambhajinagar"): (115, 80),
    ("Chhatrapati Sambhajinagar", "Jalna"): (65, 60), ("Jalna", "Wardha"): (440, 850),
    ("Wardha", "Nagpur"): (78, 60), ("Wardha", "Chandrapur"): (125, 0), ("Jalna", "Akola"): (220, 150),
    ("Akola", "Amravati"): (100, 80), ("Amravati", "Nagpur"): (155, 100), ("Jalna", "Yavatmal"): (330, 200),
    ("Yavatmal", "Wani"): (100, 0), ("Wani", "Chandrapur"): (50, 0),
}


def fill_demo_legs():
    from apps.routes.models import Leg

    now = timezone.now()
    for leg in Leg.objects.select_related("from_place", "to_place").filter(distance_km__isnull=True):
        key = (leg.from_place.name, leg.to_place.name)
        figures = DEMO_LEGS.get(key) or DEMO_LEGS.get(key[::-1])
        if not figures:
            continue
        km, tolls = figures
        leg.distance_km, leg.tolls_inr, leg.typical_minutes = Decimal(km), tolls, round(km * 0.9)
        leg.source, leg.verified_at = Leg.Source.DEMO, now
        leg.save()


class Command(BaseCommand):
    help = "Local development only: demo members, a car, demo leg figures and a sample route ride."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=1.")
        call_command("seed_reference_data")
        fill_demo_legs()
        users = []
        for phone, name, town, gender, upi in DEMO_USERS:
            user, _ = User.objects.get_or_create(
                phone=phone,
                defaults={"name": name, "hometown": town, "gender": gender, "upi_id": upi,
                          "terms_accepted_at": timezone.now()},
            )
            users.append(user)
        aditi = users[0]
        car, _ = Vehicle.objects.get_or_create(
            owner=aditi, defaults={"make_model": "Hyundai i20", "colour": "Blue", "registration": "MH31XX0000",
                                   "passenger_seats": 4},
        )
        if not Ride.objects.filter(driver=aditi, status="open").exists():
            from apps.routes.models import Place, Route
            from apps.routes.services import quote

            departure = (timezone.now() + timedelta(days=10)).replace(hour=15, minute=30, second=0, microsecond=0)
            route = Route.objects.get(slug="pune-nagpur-samruddhi-wardha")
            pune, nagpur = Place.objects.get(name="Pune"), Place.objects.get(name="Nagpur")
            create_route_ride(
                aditi, route=route, from_place=pune, to_place=nagpur, vehicle=car, departure_at=departure,
                seats_offered=3, fare_inr=quote(route, pune, nagpur, 3)["suggested_fare_inr"],
                pickup={"name": "Shivajinagar bus stand"}, dropoff_point="Nagpur railway station",
                pickup_details="Blue i20 near gate 2. Call when you arrive.",
                notes="One tea stop near Jalna. Please travel light.", policy_ack=True,
            )
        self.stdout.write(self.style.SUCCESS("Demo data ready. Phones: " + ", ".join(p for p, *_ in DEMO_USERS)))
