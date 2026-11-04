"""Create the first administrator from an interactive, access-controlled terminal."""
from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import (CommonPasswordValidator, MinimumLengthValidator,
                                                     NumericPasswordValidator, UserAttributeSimilarityValidator,
                                                     validate_password)
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.admin_dashboard.models import AdminAccount, AdminAuditEvent
from apps.admin_dashboard.permissions import AdminRole
from apps.admin_dashboard.security import encrypt_totp_secret, matching_totp_counter, parse_totp_secret


class Command(BaseCommand):
    help = "Create the initial administrator. Password and TOTP setup key are read without terminal echo."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        name = options["name"].strip()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError("Enter a valid administrator email.") from exc
        if not name or len(name) > 120:
            raise CommandError("Enter an administrator name of at most 120 characters.")
        if AdminAccount.objects.exists():
            raise CommandError("Initial administrator already exists; bootstrap is disabled.")
        password = getpass("Admin password (at least 12 characters): ")
        repeat = getpass("Repeat admin password: ")
        if len(password) < 12 or len(password) > 1024 or password != repeat:
            raise CommandError("Passwords must match and be 12 to 1024 characters long.")
        try:
            validate_password(password, user=AdminAccount(email=email, name=name), password_validators=[
                MinimumLengthValidator(min_length=12), CommonPasswordValidator(), NumericPasswordValidator(),
                UserAttributeSimilarityValidator(user_attributes=["email", "name"]),
            ])
        except ValidationError:
            raise CommandError("Choose a stronger password that does not resemble your name or email.") from None
        setup_key = getpass("TOTP setup key (base32): ")
        code = getpass("Current 6-digit authenticator code: ")
        try:
            secret = parse_totp_secret(setup_key)
            encrypted_secret = encrypt_totp_secret(secret)
        except (ValueError, ImproperlyConfigured):
            # Never include setup-key input or the cryptographic exception in console output.
            raise CommandError("Could not validate TOTP setup or encryption configuration.") from None
        counter = matching_totp_counter(secret, code, timezone.now().timestamp(), -1)
        if counter is None:
            raise CommandError("Authenticator code did not match the setup key.")
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [786987746])
            if AdminAccount.objects.exists():
                raise CommandError("Initial administrator already exists; bootstrap is disabled.")
            admin = AdminAccount.objects.create(
                email=email, name=name, role=AdminRole.SUPER_ADMIN,
                password_hash=make_password(password), totp_secret_encrypted=encrypted_secret,
                last_totp_counter=counter,
            )
            AdminAuditEvent.objects.create(admin=admin, admin_role=admin.role, action="admin_bootstrapped")
        self.stdout.write(self.style.SUCCESS("Initial administrator created. Wait for the next authenticator code to sign in."))
