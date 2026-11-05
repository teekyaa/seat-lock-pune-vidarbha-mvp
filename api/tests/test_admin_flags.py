from datetime import timedelta

import pytest
from django.utils import timezone
from django.core.cache import cache
from django.db import DatabaseError
from rest_framework.test import APIClient

from apps.admin_dashboard.models import AdminAuditEvent, AdminSession, FeatureFlag, FeatureFlagChange
from apps.admin_dashboard.permissions import AdminRole
from apps.admin_dashboard.security import token_hash
from apps.bookings import services, sweeps
from apps.bookings.models import WaitlistEntry
from tests.test_admin_auth import admin_account, login
from tests.test_api import client_for

pytestmark = pytest.mark.django_db
KEY = 'bookings.new_bookings_enabled'


def authenticated(admin_account, role):
    account, secret = admin_account
    account.role = role
    account.save(update_fields=['role'])
    client = APIClient()
    token = login(client, secret).data['token']
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    return client, token


def test_only_super_admin_can_toggle_and_repeat_is_idempotent(admin_account, ride, rahul):
    viewer, _ = authenticated(admin_account, AdminRole.VIEWER)
    body = {'value': False, 'reason': 'Pause for maintenance', 'confirmation': KEY}
    assert viewer.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json').status_code == 403
    assert FeatureFlag.objects.get(pk=KEY).value is True

    account, _ = admin_account
    account.role = AdminRole.SUPER_ADMIN
    account.save(update_fields=['role'])
    assert viewer.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json').status_code == 200
    assert client_for(rahul).post(f'/api/v1/rides/{ride.code}/request', {'policy_ack': True}, format='json').status_code == 503
    assert viewer.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json').status_code == 200
    assert FeatureFlagChange.objects.filter(flag_id=KEY).count() == 1
    event = AdminAuditEvent.objects.get(action='feature_flag_changed')
    assert event.before == {'value': True} and event.after == {'value': False}
    assert event.reason == 'Pause for maintenance'


def test_toggle_requires_recent_reauthentication_and_exact_confirmation(admin_account):
    client, token = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    body = {'value': False, 'reason': 'Maintenance', 'confirmation': 'wrong'}
    assert client.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json').status_code == 400
    body['confirmation'] = KEY
    AdminSession.objects.filter(token_hash=token_hash(token)).update(reauthenticated_at=timezone.now() - timedelta(minutes=11))
    response = client.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json')
    assert response.status_code == 403 and response.data['error']['code'] == 'ADMIN_REAUTH_REQUIRED'
    assert FeatureFlag.objects.get(pk=KEY).value is True


def test_flag_change_rolls_back_if_audit_fails(admin_account, monkeypatch):
    client, _ = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr('apps.admin_dashboard.api.record_event', fail)
    with pytest.raises(RuntimeError):
        client.post(f'/api/v1/admin/feature-flags/{KEY}/change',
                    {'value': False, 'reason': 'Maintenance', 'confirmation': KEY}, format='json')
    assert FeatureFlag.objects.get(pk=KEY).value is True
    assert not FeatureFlagChange.objects.filter(flag_id=KEY).exists()


def test_waitlist_resumes_after_booking_pause(make_ride, rahul, neha, confirm, clock):
    ride = make_ride(seats=1)
    booking = confirm(ride, rahul)
    entry = services.join_waitlist(ride, neha)
    FeatureFlag.objects.filter(pk=KEY).update(value=False)
    services.cancel_by_passenger(booking, rahul)
    entry.refresh_from_db()
    assert entry.status == WaitlistEntry.Status.WAITING
    FeatureFlag.objects.filter(pk=KEY).update(value=True)
    assert sweeps.resume_waitlists(clock.now) == 1
    entry.refresh_from_db()
    assert entry.status == WaitlistEntry.Status.OFFERED


def test_ride_posting_flag_enforced_at_api(admin_account, driver, car, pair, clock, policy):
    client, _ = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    key = 'rides.new_ride_creation_enabled'
    body = {'value': False, 'reason': 'Maintenance', 'confirmation': key}
    assert client.post(f'/api/v1/admin/feature-flags/{key}/change', body, format='json').status_code == 200
    ride = {'city_pair': pair.pk, 'vehicle': car.pk, 'departure_at': (clock.now + timedelta(days=4)).isoformat(),
            'seats_offered': 3, 'fare_inr': 0, 'pickup_point': 'A', 'dropoff_point': 'B', 'policy_ack': True}
    assert client_for(driver).post('/api/v1/rides', ride, format='json').status_code == 503
    body['value'] = True
    assert client.post(f'/api/v1/admin/feature-flags/{key}/change', body, format='json').status_code == 200
    assert client_for(driver).post('/api/v1/rides', ride, format='json').status_code == 201


def test_control_history_masks_reasons_from_viewers(admin_account):
    client, _ = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    body = {'value': False, 'reason': 'Internal investigation', 'confirmation': KEY}
    assert client.post(f'/api/v1/admin/feature-flags/{KEY}/change', body, format='json').status_code == 200
    response = client.get(f'/api/v1/admin/feature-flags/{KEY}/history')
    assert response.status_code == 200 and response.data[0]['reason'] == 'Internal investigation'
    account, _ = admin_account
    account.role = AdminRole.VIEWER
    account.save(update_fields=['role'])
    response = client.get(f'/api/v1/admin/feature-flags/{KEY}/history')
    assert response.status_code == 200 and response.data[0]['reason'] is None


def test_ops_can_toggle_signup_but_not_critical_controls(admin_account):
    client, _ = authenticated(admin_account, AdminRole.OPS_ADMIN)
    key = 'signup.new_signups_enabled'
    body = {'value': False, 'reason': 'Maintenance', 'confirmation': key}
    assert client.post(f'/api/v1/admin/feature-flags/{key}/change', body, format='json').status_code == 200
    critical = {'value': False, 'reason': 'Maintenance', 'confirmation': KEY}
    assert client.post(f'/api/v1/admin/feature-flags/{KEY}/change', critical, format='json').status_code == 403


def test_signup_pause_keeps_existing_login_available(rahul):
    from apps.accounts.auth import hash_otp
    from apps.accounts.models import OTPChallenge, User
    key = 'signup.new_signups_enabled'
    FeatureFlag.objects.filter(pk=key).update(value=False)
    cache.clear()
    client = APIClient()
    code = '123456'
    for phone, expected in ((rahul.phone, 200), ('+919876543210', 503)):
        OTPChallenge.objects.create(phone=phone, code_hash=hash_otp(phone, code),
                                    expires_at=timezone.now() + timedelta(minutes=5))
        assert client.post('/api/v1/auth/otp/verify', {'phone': phone, 'code': code}, format='json').status_code == expected
    assert not User.objects.filter(phone='+919876543210').exists()


def test_noncritical_flag_falls_back_to_database_when_cache_fails(monkeypatch):
    from apps.admin_dashboard.flags import is_enabled
    key = 'signup.new_signups_enabled'
    FeatureFlag.objects.filter(pk=key).update(value=False)
    def fail(*args, **kwargs):
        raise ConnectionError('cache unavailable')
    monkeypatch.setattr('apps.admin_dashboard.flags.cache.get', fail)
    monkeypatch.setattr('apps.admin_dashboard.flags.cache.set', fail)
    assert is_enabled(key) is False


def test_noncritical_flag_uses_declared_default_when_database_unavailable(monkeypatch):
    from apps.admin_dashboard.flags import is_enabled
    monkeypatch.setattr('apps.admin_dashboard.flags.cache.get', lambda *args, **kwargs: None)
    def fail(*args, **kwargs):
        raise DatabaseError('database unavailable')
    monkeypatch.setattr('apps.admin_dashboard.flags.FeatureFlag.objects.filter', fail)
    assert is_enabled('signup.new_signups_enabled') is True
