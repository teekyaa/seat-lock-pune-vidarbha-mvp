import pytest
import os
import subprocess
import sys
from rest_framework.test import APIClient
from django.core.cache import cache

from apps.notifications.channels import valid_push_endpoint
from tests.test_api import client_for


@pytest.mark.django_db
def test_otp_verification_is_ip_limited(settings):
    cache.clear()
    settings.OTP_VERIFY_ATTEMPTS_PER_IP = 2
    client = APIClient()
    for _ in range(2):
        assert client.post('/api/v1/auth/otp/verify', {'phone': 'not-a-phone', 'code': '0'}, format='json').status_code == 400
    assert client.post('/api/v1/auth/otp/verify', {'phone': 'not-a-phone', 'code': '0'}, format='json').status_code == 429


@pytest.mark.parametrize('url,allowed', [
    ('https://fcm.googleapis.com/fcm/send/example', True),
    ('https://updates.push.services.mozilla.com/wpush/example', True),
    ('http://127.0.0.1:8001/admin/', False),
    ('https://fcm.googleapis.com.evil.example/a', False),
    ('https://fcm.googleapis.com@evil.example/a', False),
    ('https://fcm.googleapis.com:444/a', False),
])
def test_push_endpoint_allowlist(url, allowed):
    assert valid_push_endpoint(url) is allowed


@pytest.mark.django_db
def test_subscription_rejects_internal_endpoint(driver):
    response = client_for(driver).post('/api/v1/push/subscriptions', {
        'endpoint': 'http://127.0.0.1:8001/admin/', 'keys': {'p256dh': 'x', 'auth': 'y'}
    }, format='json')
    assert response.status_code == 400


@pytest.mark.django_db
def test_booking_rejects_string_policy_ack(ride, rahul):
    response = client_for(rahul).post(f'/api/v1/rides/{ride.code}/request', {'policy_ack': 'false'}, format='json')
    assert response.status_code == 400


@pytest.mark.django_db
def test_driver_cannot_confirm_an_expired_unpaid_hold(ride, rahul, clock):
    from datetime import timedelta
    from apps.bookings import services
    from apps.core.errors import Conflict

    booking = services.request_seat(ride, rahul, policy_ack=True)
    services.accept(booking, ride.driver)
    clock.advance(hours=3)
    with pytest.raises(Conflict) as error:
        services.confirm_advance(booking, ride.driver)
    assert error.value.code == 'hold_expired'


@pytest.mark.django_db
def test_readiness_fails_closed_when_cache_is_unavailable(monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError('private connection details')
    monkeypatch.setattr('seatlock.urls.cache.set', fail)
    response = APIClient().get('/readyz')
    assert response.status_code == 503
    assert response.json() == {'ready': False}


def test_synthetic_load_seed_rejects_unapproved_database():
    from django.core.management import call_command
    from django.core.management.base import CommandError
    with pytest.raises(CommandError):
        call_command('seed_loadtest', users=2)


def test_production_configuration_rejects_sqlite():
    env = os.environ.copy()
    env.update(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='x' * 64, DATABASE_URL='sqlite:///:memory:',
               REDIS_URL='redis://127.0.0.1:6379/0')
    process = subprocess.run([sys.executable, '-c', 'import seatlock.settings'], env=env,
                             capture_output=True, text=True, timeout=10)
    assert process.returncode != 0
    assert 'Production requires a PostgreSQL DATABASE_URL' in process.stderr


def test_production_configuration_rejects_short_secret():
    env = os.environ.copy()
    env.update(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='change-me')
    process = subprocess.run([sys.executable, '-c', 'import seatlock.settings'], env=env,
                             capture_output=True, text=True, timeout=10)
    assert process.returncode != 0
    assert 'strong DJANGO_SECRET_KEY' in process.stderr
