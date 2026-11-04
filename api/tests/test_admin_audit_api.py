import pytest

from apps.admin_dashboard.models import AdminAuditEvent
from apps.admin_dashboard.permissions import AdminRole
from tests.test_admin_auth import admin_account
from tests.test_admin_flags import authenticated

pytestmark = pytest.mark.django_db


def test_audit_log_is_permission_gated_and_cursor_paginated(admin_account):
    client, _ = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    for index in range(5):
        AdminAuditEvent.objects.create(action='synthetic_event', resource_type='test', resource_id=str(index))
    first = client.get('/api/v1/admin/audit-logs?action=synthetic_event&limit=2')
    assert first.status_code == 200 and len(first.data['results']) == 2
    cursor = first.data['next_cursor']
    second = client.get('/api/v1/admin/audit-logs', {'action': 'synthetic_event', 'limit': 2, 'cursor': cursor})
    assert second.status_code == 200 and len(second.data['results']) == 2
    assert {row['id'] for row in first.data['results']}.isdisjoint({row['id'] for row in second.data['results']})
    assert client.get('/api/v1/admin/audit-logs?limit=101').status_code == 400
    assert client.get('/api/v1/admin/audit-logs?cursor=invalid').status_code == 400
    account, _ = admin_account
    account.role = AdminRole.VIEWER
    account.save(update_fields=['role'])
    assert client.get('/api/v1/admin/audit-logs').status_code == 403


def test_audit_response_redacts_sensitive_fields_and_text(admin_account):
    client, _ = authenticated(admin_account, AdminRole.SUPER_ADMIN)
    AdminAuditEvent.objects.create(action='redaction_test', resource_type='test',
        before={'phone': '9876543210', 'note': 'otp: 123456'},
        after={'email': 'test@example.com'}, reason='Contact test@example.com')
    response = client.get('/api/v1/admin/audit-logs?action=redaction_test')
    assert response.status_code == 200
    row = response.data['results'][0]
    assert row['before'] == {'phone': '[REDACTED]', 'note': '[REDACTED]'}
    assert row['after'] == {'email': '[REDACTED]'}
    assert row['reason'] == 'Contact [REDACTED]'
