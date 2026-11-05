"""Create synthetic accounts in an explicitly named, isolated test database only."""
import json
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from apps.accounts.auth import issue_token
from apps.accounts.models import User, Vehicle
from apps.core.models import CityPair, PolicyVersion
from apps.rides.models import Ride
from apps.rides.services import advance_for, fare_quote


class Command(BaseCommand):
    help = "Create synthetic load-test data in the dedicated seatlock_loadtest PostgreSQL database."

    def add_arguments(self, parser):
        parser.add_argument('--confirm-isolated', action='store_true')
        parser.add_argument('--users', type=int, default=500)

    def handle(self, *args, **options):
        if (not settings.DEBUG or connection.vendor != 'postgresql' or
                connection.settings_dict['NAME'] != 'seatlock_loadtest' or not options['confirm_isolated']):
            raise CommandError('Requires DEBUG, PostgreSQL database seatlock_loadtest, and --confirm-isolated.')
        count = options['users']
        if not 2 <= count <= 5000:
            raise CommandError('Choose 2 to 5000 synthetic users.')
        call_command('seed_reference_data', verbosity=0)
        pair = CityPair.objects.filter(active=True).first()
        policy = PolicyVersion.current()
        now = timezone.now()
        output_dir = settings.BASE_DIR / '.loadtest'
        output_dir.mkdir(exist_ok=True)
        accounts = []
        rides = []
        for i in range(count):
            phone = '+919' + f'{i:09d}'
            user, _ = User.objects.get_or_create(phone=phone, defaults={
                'name': f'Synthetic {i}', 'hometown': 'Pune', 'terms_accepted_at': now, 'upi_id': 'test@bank',
            })
            vehicle, _ = Vehicle.objects.get_or_create(owner=user, registration=f'MH12AB{i % 10000:04d}',
                                                        defaults={'make_model': 'Synthetic', 'passenger_seats': 4})
            accounts.append({'token': issue_token(user), 'vehicle': vehicle.pk, 'user_id': str(user.pk)})
            if i < min(50, count):
                fare = fare_quote(pair, 3, policy)['max_fare_inr']
                departure = now + timedelta(days=7)
                ride = Ride.objects.create(driver=user, vehicle=vehicle, city_pair=pair, policy_version=policy,
                    departure_at=departure, original_departure_at=departure,
                    expected_arrival_at=departure + timedelta(hours=pair.typical_duration_hours),
                    pickup_point='Synthetic pickup', dropoff_point='Synthetic dropoff', seats_offered=3,
                    suggested_fare_inr=fare, fare_inr=fare, advance_inr=advance_for(fare, policy))
                rides.append({'code': ride.code, 'driver_id': str(user.pk)})
        (output_dir / 'accounts.json').write_text(json.dumps({'accounts': accounts, 'rides': rides, 'pair': pair.pk}), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Created {count} synthetic accounts; credentials saved in ignored api/.loadtest/.'))
