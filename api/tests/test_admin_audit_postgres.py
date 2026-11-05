import pytest
import uuid
from django.db import DatabaseError, connection, transaction

from apps.admin_dashboard.models import AdminAuditEvent

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='audit trigger requires PostgreSQL'),
]


def test_database_rejects_audit_update_and_delete():
    event = AdminAuditEvent.objects.create(action='test')
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AdminAuditEvent.objects.filter(pk=event.pk).update(action='changed')
    with pytest.raises(DatabaseError):
        with transaction.atomic():
            AdminAuditEvent.objects.filter(pk=event.pk).delete()
    assert AdminAuditEvent.objects.filter(pk=event.pk, action='test').exists()


def test_restricted_runtime_role_can_insert_but_not_change_audit_events():
    role = 'audit_test_' + uuid.uuid4().hex[:12]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT SELECT, INSERT ON TABLE admin_dashboard_adminauditevent TO "{role}"')
            cursor.execute(f'SET LOCAL ROLE "{role}"')
        event = AdminAuditEvent.objects.create(action='test')
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                AdminAuditEvent.objects.filter(pk=event.pk).update(action='changed')
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                AdminAuditEvent.objects.filter(pk=event.pk).delete()
        with connection.cursor() as cursor:
            cursor.execute('RESET ROLE')
        transaction.set_rollback(True)
