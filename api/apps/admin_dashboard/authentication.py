from datetime import timedelta

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import AdminSession
from .security import token_hash

SESSION_IDLE_MINUTES = 30
SESSION_ABSOLUTE_HOURS = 12


class AdminSessionAuthentication(authentication.BaseAuthentication):
    """Authenticate only the separate admin token, never a rider bearer token."""

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0] != b"AdminBearer":
            return None
        if len(header) != 2 or len(header[1]) > 200:
            raise exceptions.AuthenticationFailed("Admin session has ended.")
        try:
            raw = header[1].decode("ascii")
        except UnicodeDecodeError:
            raise exceptions.AuthenticationFailed("Admin session has ended.") from None
        now = timezone.now()
        session = AdminSession.objects.select_related("admin").filter(token_hash=token_hash(raw)).first()
        if (not session or session.revoked_at or not session.admin.is_active or session.expires_at <= now or
                session.last_activity_at <= now - timedelta(minutes=SESSION_IDLE_MINUTES)):
            raise exceptions.AuthenticationFailed("Admin session has ended.")
        active = AdminSession.objects.filter(
            pk=session.pk, revoked_at__isnull=True, admin__is_active=True, expires_at__gt=now,
            last_activity_at__gt=now - timedelta(minutes=SESSION_IDLE_MINUTES),
        )
        # Automatic dashboard polling must not keep an idle operator signed in indefinitely.
        if request.META.get("HTTP_X_ADMIN_BACKGROUND") == "1" and request.method == "GET":
            changed = active.exists()
        else:
            changed = active.update(last_activity_at=now)
        if not changed:
            raise exceptions.AuthenticationFailed("Admin session has ended.")
        return session.admin, session

    def authenticate_header(self, request):
        return "AdminBearer"
