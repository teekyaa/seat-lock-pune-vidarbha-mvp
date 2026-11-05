"""Cryptographic helpers for administrator credentials. Never log their inputs."""
import base64
import hashlib
import hmac
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.twofactor.totp import TOTP
from django.core.exceptions import ImproperlyConfigured

TOTP_PERIOD_SECONDS = 30


def _cipher() -> Fernet:
    value = os.environ.get("ADMIN_TOTP_ENCRYPTION_KEY", "")
    try:
        return Fernet(value.encode("ascii"))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise ImproperlyConfigured("ADMIN_TOTP_ENCRYPTION_KEY must be a valid Fernet key.") from exc


def validate_security_configuration() -> None:
    _cipher()


def encrypt_totp_secret(secret: bytes) -> str:
    return _cipher().encrypt(secret).decode("ascii")


def decrypt_totp_secret(ciphertext: str) -> bytes:
    try:
        return _cipher().decrypt(ciphertext.encode("ascii"))
    except (InvalidToken, UnicodeError) as exc:
        raise ImproperlyConfigured("Admin TOTP secret cannot be decrypted.") from exc


def parse_totp_secret(value: str) -> bytes:
    try:
        text = value.strip().replace(" ", "").upper()
        key = base64.b32decode(text + "=" * (-len(text) % 8), casefold=True)
        if len(key) < 20:
            raise ValueError("TOTP secret is too short")
        return key
    except (ValueError, TypeError) as exc:
        raise ValueError("Invalid TOTP setup key.") from exc


def matching_totp_counter(secret: bytes, code: str, timestamp: float, last_counter: int) -> int | None:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return None
    totp = TOTP(secret, 6, hashes.SHA1(), TOTP_PERIOD_SECONDS)
    current = int(timestamp // TOTP_PERIOD_SECONDS)
    for counter in (current, current - 1, current + 1):
        if counter > last_counter and counter >= 0:
            generated = totp.generate(counter * TOTP_PERIOD_SECONDS).decode("ascii")
            if hmac.compare_digest(generated, code):
                return counter
    return None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
