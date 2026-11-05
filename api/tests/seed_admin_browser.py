"""Seed only the disposable SQLite database used by the local admin browser test."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'seatlock.settings')
import django
django.setup()

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import connection

from apps.admin_dashboard.models import AdminAccount
from apps.admin_dashboard.permissions import AdminRole
from apps.admin_dashboard.security import encrypt_totp_secret

if (not settings.DEBUG or os.environ.get('ADMIN_E2E_ENABLED') != '1' or
        connection.vendor != 'sqlite' or Path(connection.settings_dict['NAME']).name != '.admin-browser-test.sqlite3'):
    raise RuntimeError('Refusing to seed outside the disposable admin browser-test database.')

password = os.environ['ADMIN_E2E_PASSWORD']
secret = os.environ['ADMIN_E2E_SECRET'].encode('ascii')
if len(password) < 12 or len(secret) < 16:
    raise RuntimeError('Synthetic test credentials are missing or too short.')
AdminAccount.objects.create(email='admin@example.invalid', name='Synthetic admin', role=AdminRole.SUPER_ADMIN,
                            password_hash=make_password(password), totp_secret_encrypted=encrypt_totp_secret(secret))
