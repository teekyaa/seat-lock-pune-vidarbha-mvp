import json
import logging

from apps.admin_dashboard.logging import AdminJSONFormatter


def test_admin_structured_logging_redacts_nested_secrets_and_identifiers():
    record = logging.LogRecord('seatlock.admin', logging.INFO, __file__, 1, 'ignored', (), None)
    record.event = 'permission_denied'
    record.request_id = 'synthetic-request-id'
    record.context = {'password': 'test-password', 'nested': {'otp': '123456', 'phone': '+919876543210'},
                      'note': 'contact person@example.invalid or 9876543210', 'admin_id': 'synthetic-id'}
    raw = AdminJSONFormatter().format(record)
    parsed = json.loads(raw)
    assert parsed['event'] == 'permission_denied'
    assert parsed['context']['admin_id'] == 'synthetic-id'
    for value in ('test-password', '123456', '+919876543210', 'person@example.invalid', '9876543210'):
        assert value not in raw
