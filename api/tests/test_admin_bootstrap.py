import base64
import io

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.admin_dashboard.models import AdminAccount, AdminAuditEvent

pytestmark = pytest.mark.django_db


def test_bootstrap_is_interactive_one_time_and_does_not_print_secrets(monkeypatch):
    monkeypatch.setenv('ADMIN_TOTP_ENCRYPTION_KEY', Fernet.generate_key().decode())
    secret = b'synthetic-test-secret-32-bytes!!'
    setup = base64.b32encode(secret).decode()
    code = TOTP(secret, 6, hashes.SHA1(), 30).generate(timezone.now().timestamp()).decode()
    answers = iter(['a sufficiently long password', 'a sufficiently long password', setup, code])
    monkeypatch.setattr('apps.admin_dashboard.management.commands.bootstrap_admin.getpass', lambda prompt: next(answers))
    output = io.StringIO()
    call_command('bootstrap_admin', email='Admin@Example.invalid', name='Admin', stdout=output)
    account = AdminAccount.objects.get()
    assert account.email == 'admin@example.invalid'
    assert account.role == 'SUPER_ADMIN'
    assert setup not in output.getvalue() and code not in output.getvalue()
    assert setup not in account.totp_secret_encrypted
    assert AdminAuditEvent.objects.filter(action='admin_bootstrapped', admin=account).count() == 1
    with pytest.raises(CommandError):
        call_command('bootstrap_admin', email='other@example.invalid', name='Other', stdout=output)
