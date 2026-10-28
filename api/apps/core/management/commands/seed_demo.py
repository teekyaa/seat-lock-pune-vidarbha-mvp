from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.accounts.models import User, Vehicle
from apps.core.models import CityPair
from apps.rides.models import Ride
from apps.rides.services import create_ride

# Synthetic people only. Sign in as any of them with the console OTP.
DEMO_USERS = [
    ("+919000010001", "Aditi Deshmukh", "Nagpur", "female", "aditi.demo@okaxis"),
    ("+919000010002", "Rahul Patil", "Wardha", "male", "rahul.demo@okhdfc"),
    ("+919000010003", "Neha Kulkarni", "Wardha", "female", "neha.demo@oksbi"),
]


class Command(BaseCommand):
    help = "Local development only: demo members, a car and a sample Pune to Nagpur ride."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=1.")
        call_command("seed_reference_data")
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
            departure = (timezone.now() + timedelta(days=10)).replace(hour=15, minute=30, second=0, microsecond=0)
            pair = CityPair.objects.get(origin="Pune", destination="Nagpur")
            create_ride(
                aditi, city_pair=pair, vehicle=car, departure_at=departure, seats_offered=3, fare_inr=1500,
                pickup_point="Shivajinagar bus stand", dropoff_point="Nagpur railway station",
                pickup_details="Blue i20 near gate 2. Call when you arrive.",
                notes="One tea stop near Amravati. Please travel light.", policy_ack=True,
            )
        self.stdout.write(self.style.SUCCESS("Demo data ready. Phones: " + ", ".join(p for p, *_ in DEMO_USERS)))
