import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import AuthToken


def hash_token(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_otp(phone, code):
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_token(user):
    raw = secrets.token_urlsafe(32)
    AuthToken.objects.create(
        user=user,
        key_hash=hash_token(raw),
        expires_at=timezone.now() + timedelta(days=settings.AUTH_TOKEN_TTL_DAYS),
    )
    return raw


class BearerTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode()
        if not header.startswith(f"{self.keyword} "):
            return None
        raw = header[len(self.keyword) + 1 :].strip()
        token = AuthToken.objects.select_related("user").filter(key_hash=hash_token(raw)).first()
        if not token or token.expires_at <= timezone.now() or not token.user.is_active:
            raise exceptions.AuthenticationFailed("Your session has ended. Please sign in again.")
        now = timezone.now()
        if not token.last_used_at or now - token.last_used_at > timedelta(minutes=5):
            AuthToken.objects.filter(pk=token.pk).update(last_used_at=now)
        return token.user, token

    def authenticate_header(self, request):
        return self.keyword
