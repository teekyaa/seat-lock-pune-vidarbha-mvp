import threading

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.db import connection, connections
from django.utils import timezone
from rest_framework.test import APIClient

from apps.admin_dashboard.models import AdminAccount, AdminSession
from apps.admin_dashboard.permissions import AdminRole
from apps.admin_dashboard.security import encrypt_totp_secret

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='TOTP replay concurrency requires PostgreSQL'),
]


def test_same_totp_cannot_create_two_concurrent_sessions(monkeypatch):
    monkeypatch.setenv('ADMIN_TOTP_ENCRYPTION_KEY', Fernet.generate_key().decode())
    cache.clear()
    secret = b'synthetic-admin-secret-for-concurrent-testing'
    account = AdminAccount.objects.create(email='synthetic@example.invalid', name='Synthetic', role=AdminRole.VIEWER,
        password_hash=make_password('synthetic test-only password'), totp_secret_encrypted=encrypt_totp_secret(secret))
    code = TOTP(secret, 6, hashes.SHA1(), 30).generate(timezone.now().timestamp()).decode()
    barrier = threading.Barrier(2, timeout=15)
    results = []

    def attempt():
        try:
            client = APIClient()
            barrier.wait()
            response = client.post('/api/v1/admin/auth/login', {
                'email': account.email, 'password': 'synthetic test-only password', 'code': code,
            }, format='json')
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(results) == [200, 401]
    assert AdminSession.objects.filter(admin=account).count() == 1
