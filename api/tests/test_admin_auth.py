from datetime import timedelta

import pytest
import os
import ipaddress
import subprocess
import sys
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient, APIRequestFactory

from apps.admin_dashboard.api import AdminAPIView
from apps.admin_dashboard.models import AdminAccount, AdminAuditEvent, AdminSession
from apps.admin_dashboard.permissions import AdminRole, Permission
from apps.admin_dashboard.security import encrypt_totp_secret, token_hash
from tests.test_api import client_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_account(monkeypatch):
    cache.clear()
    monkeypatch.setenv('ADMIN_TOTP_ENCRYPTION_KEY', Fernet.generate_key().decode())
    secret = b'test-only-secret-with-32-bytes!!'
    account = AdminAccount.objects.create(email='operator@example.invalid', name='Operator', role=AdminRole.VIEWER,
                                          password_hash=make_password('a long test-only password'),
                                          totp_secret_encrypted=encrypt_totp_secret(secret))
    return account, secret


def login(client, secret, *, password='a long test-only password'):
    code = TOTP(secret, 6, hashes.SHA1(), 30).generate(timezone.now().timestamp()).decode()
    return client.post('/api/v1/admin/auth/login', {
        'email': 'operator@example.invalid', 'password': password, 'code': code,
    }, format='json')


def test_separate_login_me_and_logout(admin_account):
    account, secret = admin_account
    client = APIClient()
    response = login(client, secret)
    assert response.status_code == 200
    token = response.data['token']
    assert not AdminSession.objects.filter(token_hash=token).exists()
    assert AdminSession.objects.filter(token_hash=token_hash(token), admin=account).exists()
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    assert client.get('/api/v1/admin/me').data['role'] == AdminRole.VIEWER
    assert client.get('/api/v1/admin/overview').status_code == 200
    assert client.post('/api/v1/admin/auth/logout').status_code == 204
    assert client.get('/api/v1/admin/me').status_code == 401
    assert set(AdminAuditEvent.objects.values_list('action', flat=True)) == {'admin_login_succeeded', 'admin_logout'}


def test_admin_code_is_single_use_and_wrong_password_fails(admin_account):
    _, secret = admin_account
    client = APIClient()
    assert login(client, secret, password='wrong-password').status_code == 401
    assert login(client, secret).status_code == 200
    assert login(client, secret).status_code == 401
    assert AdminSession.objects.count() == 1


def test_rider_token_does_not_access_admin(rahul):
    assert client_for(rahul).get('/api/v1/admin/overview').status_code == 401
    assert APIClient().get('/api/v1/admin/overview').status_code == 401


def test_idle_and_absolute_session_expiry(admin_account):
    _, secret = admin_account
    client = APIClient()
    token = login(client, secret).data['token']
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    AdminSession.objects.filter(token_hash=token_hash(token)).update(last_activity_at=timezone.now() - timedelta(minutes=31))
    assert client.get('/api/v1/admin/me').status_code == 401
    AdminSession.objects.filter(token_hash=token_hash(token)).update(last_activity_at=timezone.now(),
                                                                     expires_at=timezone.now() - timedelta(seconds=1))
    assert client.get('/api/v1/admin/me').status_code == 401


def test_deactivation_revokes_existing_session(admin_account):
    account, secret = admin_account
    client = APIClient()
    token = login(client, secret).data['token']
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    account.is_active = False
    account.save(update_fields=['is_active'])
    assert client.get('/api/v1/admin/me').status_code == 401
    account.is_active = True
    account.save(update_fields=['is_active'])
    assert client.get('/api/v1/admin/me').status_code == 401


def test_background_refresh_does_not_extend_idle_session(admin_account, clock):
    _, secret = admin_account
    client = APIClient()
    token = login(client, secret).data['token']
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    session = AdminSession.objects.get(token_hash=token_hash(token))
    initial = session.last_activity_at
    clock.advance(minutes=5)
    assert client.get('/api/v1/admin/overview', HTTP_X_ADMIN_BACKGROUND='1').status_code == 200
    session.refresh_from_db()
    assert session.last_activity_at == initial
    assert client.get('/api/v1/admin/overview').status_code == 200
    session.refresh_from_db()
    assert session.last_activity_at > initial
    clock.advance(minutes=31)
    assert client.get('/api/v1/admin/overview', HTTP_X_ADMIN_BACKGROUND='1').status_code == 401


def test_reauthentication_requires_fresh_totp_and_updates_session(admin_account, clock):
    _, secret = admin_account
    client = APIClient()
    token = login(client, secret).data['token']
    client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + token)
    initial = AdminSession.objects.get(token_hash=token_hash(token)).reauthenticated_at
    clock.advance(seconds=31)
    code = TOTP(secret, 6, hashes.SHA1(), 30).generate(timezone.now().timestamp()).decode()
    body = {'password': 'a long test-only password', 'code': code}
    assert client.post('/api/v1/admin/auth/reauthenticate', body, format='json').status_code == 204
    session = AdminSession.objects.get(token_hash=token_hash(token))
    assert session.reauthenticated_at > initial
    assert client.post('/api/v1/admin/auth/reauthenticate', body, format='json').status_code == 401
    assert AdminAuditEvent.objects.filter(action='admin_reauthenticated').count() == 1


def test_login_rate_limit_stops_repeated_wrong_passwords(admin_account):
    _, secret = admin_account
    client = APIClient()
    for _ in range(5):
        assert login(client, secret, password='wrong-password').status_code == 401
    assert login(client, secret, password='wrong-password').status_code == 429
    assert not AdminSession.objects.exists()


def test_login_requires_valid_encryption_configuration(admin_account, monkeypatch):
    _, secret = admin_account
    monkeypatch.delenv('ADMIN_TOTP_ENCRYPTION_KEY', raising=False)
    assert login(APIClient(), secret).status_code == 503
    assert not AdminSession.objects.exists()


def test_login_fails_closed_when_cache_is_unavailable(admin_account, monkeypatch):
    _, secret = admin_account
    def unavailable(*args, **kwargs):
        raise ConnectionError('private server address')
    monkeypatch.setattr('apps.admin_dashboard.api.cache.add', unavailable)
    response = login(APIClient(), secret)
    assert response.status_code == 503
    assert 'private' not in str(response.data)
    assert not AdminSession.objects.exists()


def test_ip_limit_applies_to_malformed_attempts(admin_account, monkeypatch):
    monkeypatch.setattr('apps.admin_dashboard.api.LOGIN_ATTEMPTS_PER_IP', 2)
    client = APIClient()
    assert client.post('/api/v1/admin/auth/login', {}, format='json').status_code == 400
    assert client.post('/api/v1/admin/auth/login', {}, format='json').status_code == 400
    assert client.post('/api/v1/admin/auth/login', {}, format='json').status_code == 429


def test_permission_denial_is_audited(admin_account):
    _, secret = admin_account
    client = APIClient()
    token = login(client, secret).data['token']

    class RestrictedView(AdminAPIView):
        required_permission = Permission.ADMINS_MANAGE
        def get(self, request):
            return Response({'should_not': 'appear'})

    request = APIRequestFactory().get('/test', HTTP_AUTHORIZATION='AdminBearer ' + token)
    response = RestrictedView.as_view()(request)
    assert response.status_code == 403
    assert AdminAuditEvent.objects.filter(action='permission_denied').count() == 1


def test_missing_permission_fails_closed(admin_account):
    _, secret = admin_account
    token = login(APIClient(), secret).data['token']

    class UnmarkedView(AdminAPIView):
        def get(self, request):
            return Response({})

    request = APIRequestFactory().get('/test', HTTP_AUTHORIZATION='AdminBearer ' + token)
    assert UnmarkedView.as_view()(request).status_code == 403


def test_admin_route_permission_declarations():
    from apps.admin_dashboard.api import AdminAPIView
    from apps.admin_dashboard.urls import urlpatterns
    views = [pattern.callback.view_class for pattern in urlpatterns]
    assert views
    for view in views:
        assert issubclass(view, AdminAPIView)
        assert getattr(view, 'public_endpoint', False) or view.required_permission in Permission


def test_every_protected_admin_endpoint_rejects_anonymous_and_disallowed_roles(admin_account):
    from apps.admin_dashboard.permissions import has_permission
    from apps.admin_dashboard.urls import urlpatterns
    account, _ = admin_account
    for pattern in urlpatterns:
        view = pattern.callback.view_class
        if getattr(view, 'public_endpoint', False):
            continue
        path = '/api/v1/admin/' + str(pattern.pattern).replace('<str:key>', 'rides.new_ride_creation_enabled')
        methods = [method for method in ('get', 'post', 'patch', 'delete') if method in view.__dict__]
        for method in methods:
            anonymous = getattr(APIClient(), method)(path, {}, format='json')
            assert anonymous.status_code == 401, (path, method)
            assert anonymous.data['error']['code'] == 'ADMIN_AUTH_REQUIRED'
            assert anonymous['X-Request-ID']
            denied = next((role for role in AdminRole if not has_permission(role, view.required_permission)), None)
            if denied is None:
                continue
            account.role = denied
            account.save(update_fields=['role'])
            raw_token = 'synthetic-admin-test-token'
            AdminSession.objects.filter(token_hash=token_hash(raw_token)).delete()
            now = timezone.now()
            AdminSession.objects.create(admin=account, token_hash=token_hash(raw_token), last_activity_at=now,
                                        reauthenticated_at=now, expires_at=now + timedelta(hours=12))
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION='AdminBearer ' + raw_token)
            forbidden = getattr(client, method)(path, {}, format='json')
            assert forbidden.status_code == 403, (path, method, denied)


def test_admin_ip_allowlist_denies_unlisted_address(settings):
    settings.ADMIN_IP_ALLOWLIST = [ipaddress.ip_network('203.0.113.0/24')]
    response = APIClient().get('/api/v1/admin/overview', REMOTE_ADDR='192.0.2.1')
    assert response.status_code == 403
    assert AdminAuditEvent.objects.filter(action='admin_ip_denied').count() == 1


def test_production_admin_requires_encryption_key_at_startup():
    env = os.environ.copy()
    env.update(DJANGO_DEBUG='0', DJANGO_SECRET_KEY='x' * 64, ADMIN_DASHBOARD_ENABLED='1',
               ADMIN_TOTP_ENCRYPTION_KEY='', DATABASE_URL='postgres://test:test@127.0.0.1/test',
               REDIS_URL='redis://127.0.0.1:6379/0')
    result = subprocess.run([sys.executable, '-c', 'import seatlock.settings'], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode != 0
    assert 'ADMIN_TOTP_ENCRYPTION_KEY must be a valid Fernet key' in result.stderr


def test_failed_audit_rolls_back_login(admin_account, monkeypatch):
    account, secret = admin_account
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr('apps.admin_dashboard.api.record_event', fail)
    with pytest.raises(RuntimeError):
        login(APIClient(), secret)
    account.refresh_from_db()
    assert account.last_totp_counter == -1
    assert not AdminSession.objects.exists()
