from datetime import timedelta

import pytest
from django.utils import timezone

from apps.admin_dashboard.models import AdminAuditEvent, AdminSession, PlatformSetting
from apps.admin_dashboard.permissions import AdminRole
from apps.admin_dashboard.security import token_hash
from tests.test_admin_auth import admin_account
from tests.test_admin_flags import authenticated

pytestmark = pytest.mark.django_db
KEY = 'tickets.p0_response_minutes'
URL = f'/api/v1/admin/settings/{KEY}/change'


def test_sla_starts_unset_and_only_super_admin_can_set_it(admin_account):
    client, _ = authenticated(admin_account, AdminRole.VIEWER)
    assert client.get('/api/v1/admin/settings').status_code == 403
    assert client.post(URL, {'value': 60, 'reason': 'Approved policy'}, format='json').status_code == 403
    account, _ = admin_account
    account.role = AdminRole.SUPER_ADMIN
    account.save(update_fields=['role'])
    response = client.get('/api/v1/admin/settings')
    assert len(response.data) == 4 and all(item['value'] is None for item in response.data)
    for invalid in (-1, 0, 525601, True, '20'):
        assert client.post(URL, {'value': invalid, 'reason': 'Approved policy'}, format='json').status_code == 400
    assert client.post(URL, {'value': 60, 'reason': 'Approved policy'}, format='json').status_code == 200
    assert client.post(URL, {'value': 60, 'reason': 'Approved policy'}, format='json').status_code == 200
    event = AdminAuditEvent.objects.get(action='platform_setting_changed')
    assert event.before == {'value': None} and event.after == {'value': 60}
    assert client.post(URL, {'value': None, 'reason': 'Policy withdrawn'}, format='json').status_code == 200
    assert PlatformSetting.objects.get(pk=KEY).value is None


def test_setting_requires_recent_reauthentication_and_audit_is_atomic(admin_account, monkeypatch):
    client, token = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    session = AdminSession.objects.get(token_hash=token_hash(token))
    session.reauthenticated_at = timezone.now() - timedelta(minutes=11)
    session.save(update_fields=['reauthenticated_at'])
    body = {'value': 60, 'reason': 'Approved policy'}
    assert client.post(URL, body, format='json').status_code == 403
    session.reauthenticated_at = timezone.now()
    session.save(update_fields=['reauthenticated_at'])
    def fail(*args, **kwargs):
        raise RuntimeError('audit unavailable')
    monkeypatch.setattr('apps.admin_dashboard.api.record_event', fail)
    with pytest.raises(RuntimeError):
        client.post(URL, body, format='json')
    assert not PlatformSetting.objects.filter(pk=KEY).exists()
