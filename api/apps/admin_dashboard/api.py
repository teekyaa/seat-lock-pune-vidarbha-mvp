import hashlib
import ipaddress
import logging
import secrets
import uuid
from datetime import timedelta
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth.hashers import check_password, make_password
from django.conf import settings
from django.core.cache import cache
from django.core import signing
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from redis.exceptions import RedisError
from drf_spectacular.utils import OpenApiParameter, extend_schema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.openapi import AutoSchema

from apps.accounts.api import client_ip

from .access import RequiresAdminPermission
from .audit import record_event
from .authentication import AdminSessionAuthentication, SESSION_ABSOLUTE_HOURS
from .models import AdminAccount, AdminAuditEvent, AdminSession, FeatureFlag, FeatureFlagChange, PlatformSetting
from .logging import redact
from .flags import FLAG_DEFINITIONS, invalidate_flag
from .permissions import Permission, ROLE_PERMISSIONS, has_permission
from .platform_settings import SLA_SETTINGS, validate_setting
from .security import decrypt_totp_secret, matching_totp_counter, token_hash, validate_security_configuration
from .schemas import (AdminErrorSerializer, AdminIdentitySerializer, AdminLoginRequestSerializer,
                      AdminLoginResponseSerializer, AdminOverviewSerializer, AdminReauthenticationSerializer,
                      FeatureFlagSerializer, FeatureFlagUpdateSerializer, FeatureFlagChangeSerializer,
                      AdminAuditPageSerializer, PlatformSettingSerializer, PlatformSettingUpdateSerializer)

LOGIN_WINDOW_SECONDS = 900
LOGIN_ATTEMPTS_PER_ACCOUNT = 5
LOGIN_ATTEMPTS_PER_IP = 30
log = logging.getLogger("seatlock.admin")
_DUMMY_PASSWORD_HASH = make_password("not-an-admin-password", salt="seatlock-admin-dummy")


def _within_limit(key, limit):
    cache.add(key, 0, LOGIN_WINDOW_SECONDS)
    return cache.incr(key) <= limit


class AdminAPIView(APIView):
    schema = AutoSchema()
    authentication_classes = [AdminSessionAuthentication]
    permission_classes = [RequiresAdminPermission]
    required_permission = None

    def initial(self, request, *args, **kwargs):
        request.admin_request_id = uuid.uuid4()
        if settings.ADMIN_IP_ALLOWLIST:
            try:
                address = ipaddress.ip_address(client_ip(request))
                allowed = any(address in network for network in settings.ADMIN_IP_ALLOWLIST)
            except ValueError:
                allowed = False
            if not allowed:
                record_event(request, "admin_ip_denied", resource_type="admin_endpoint")
                raise PermissionDenied("Admin access denied.")
        super().initial(request, *args, **kwargs)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["X-Request-ID"] = str(request.admin_request_id)
        response["Cache-Control"] = "no-store"
        return response

    def handle_exception(self, exc):
        response = super().handle_exception(exc)
        codes = {401: "ADMIN_AUTH_REQUIRED", 403: "ADMIN_PERMISSION_DENIED", 429: "ADMIN_RATE_LIMITED"}
        code = codes.get(response.status_code, "ADMIN_REQUEST_INVALID")
        messages = {401: "Admin session has ended.", 403: "You do not have permission for this action.",
                    429: "Too many attempts. Try again later."}
        response.data = {"error": {"code": code, "message": messages.get(response.status_code, "Request could not be completed."),
                                   "request_id": str(self.request.admin_request_id), "details": {}}}
        return response

    def error_response(self, request, code, message, status_code):
        return Response({"error": {"code": code, "message": message,
                                   "request_id": str(request.admin_request_id), "details": {}}}, status=status_code)


class AdminLoginView(AdminAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    public_endpoint = True

    @extend_schema(request=AdminLoginRequestSerializer, responses={200: AdminLoginResponseSerializer,
                   400: AdminErrorSerializer, 401: AdminErrorSerializer, 429: AdminErrorSerializer, 503: AdminErrorSerializer})
    def post(self, request):
        try:
            validate_security_configuration()
            ip_key = hashlib.sha256(client_ip(request).encode("utf-8")).hexdigest()
            if not _within_limit(f"admin:login:ip:{ip_key}", LOGIN_ATTEMPTS_PER_IP):
                if cache.add(f"admin:lockout:ip:{ip_key}", 1, LOGIN_WINDOW_SECONDS):
                    record_event(request, "admin_login_rate_limited")
                return self.error_response(request, "ADMIN_RATE_LIMITED", "Too many sign-in attempts. Try again later.", 429)
        except (ImproperlyConfigured, ConnectionError, TimeoutError, RedisError, ValueError):
            log.warning("admin_auth_dependency_unavailable", extra={"event": "admin_auth_dependency_unavailable",
                         "request_id": str(request.admin_request_id)})
            return self.error_response(request, "ADMIN_AUTH_UNAVAILABLE", "Admin sign-in is unavailable.", 503)
        email = request.data.get("email")
        password = request.data.get("password")
        code = request.data.get("code")
        if not (isinstance(email, str) and 1 <= len(email) <= 254 and
                isinstance(password, str) and 1 <= len(password) <= 1024 and
                isinstance(code, str) and len(code) == 6 and code.isascii() and code.isdigit()):
            record_event(request, "admin_login_failed")
            return self.error_response(request, "ADMIN_INVALID_CREDENTIALS", "Invalid credentials.", 400)
        email = email.strip().lower()
        try:
            email_key = hashlib.sha256(email.encode("utf-8")).hexdigest()
            if not _within_limit(f"admin:login:account:{email_key}", LOGIN_ATTEMPTS_PER_ACCOUNT):
                if cache.add(f"admin:lockout:account:{email_key}", 1, LOGIN_WINDOW_SECONDS):
                    record_event(request, "admin_login_rate_limited")
                return self.error_response(request, "ADMIN_RATE_LIMITED", "Too many sign-in attempts. Try again later.", 429)
        except (ConnectionError, TimeoutError, RedisError, ValueError):
            log.warning("admin_rate_limit_unavailable", extra={"event": "admin_rate_limit_unavailable",
                         "request_id": str(request.admin_request_id)})
            return self.error_response(request, "ADMIN_AUTH_UNAVAILABLE", "Admin sign-in is unavailable.", 503)

        now = timezone.now()
        token = None
        account = None
        try:
            with transaction.atomic():
                account = AdminAccount.objects.select_for_update().filter(email__iexact=email).first()
                password_ok = check_password(password, account.password_hash if account else _DUMMY_PASSWORD_HASH)
                counter = None
                if account and account.is_active and password_ok:
                    counter = matching_totp_counter(decrypt_totp_secret(account.totp_secret_encrypted), code,
                                                    now.timestamp(), account.last_totp_counter)
                if account and account.is_active and password_ok and counter is not None:
                    account.last_totp_counter = counter
                    account.last_login_at = now
                    account.save(update_fields=["last_totp_counter", "last_login_at"])
                    token = secrets.token_urlsafe(32)
                    AdminSession.objects.create(
                        admin=account, token_hash=token_hash(token), last_activity_at=now, reauthenticated_at=now,
                        expires_at=now + timedelta(hours=SESSION_ABSOLUTE_HOURS),
                    )
                    record_event(request, "admin_login_succeeded", admin=account)
                else:
                    record_event(request, "admin_login_failed")
        except ImproperlyConfigured:
            return self.error_response(request, "ADMIN_AUTH_UNAVAILABLE", "Admin sign-in is unavailable.", 503)
        if token is None:
            return self.error_response(request, "ADMIN_INVALID_CREDENTIALS", "Invalid credentials.", 401)
        return Response({"token": token, "admin": {"id": str(account.pk), "name": account.name, "role": account.role}})


class AdminMeView(AdminAPIView):
    required_permission = Permission.SESSION_READ

    @extend_schema(responses={200: AdminIdentitySerializer, 401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def get(self, request):
        account = request.user
        return Response({"id": str(account.pk), "name": account.name, "role": account.role,
                         "permissions": sorted(ROLE_PERMISSIONS[account.role])})


class AdminLogoutView(AdminAPIView):
    required_permission = Permission.SESSION_LOGOUT

    @extend_schema(request=None, responses={204: None, 401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def post(self, request):
        with transaction.atomic():
            account = AdminAccount.objects.select_for_update().get(pk=request.user.pk)
            session = AdminSession.objects.select_for_update().get(pk=request.auth.pk, admin=account)
            if session.revoked_at is None:
                session.revoked_at = timezone.now()
                session.save(update_fields=["revoked_at"])
                record_event(request, "admin_logout", admin=account)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminReauthenticateView(AdminAPIView):
    required_permission = Permission.SESSION_REAUTHENTICATE

    @extend_schema(request=AdminReauthenticationSerializer,
                   responses={204: None, 400: AdminErrorSerializer, 401: AdminErrorSerializer,
                              429: AdminErrorSerializer, 503: AdminErrorSerializer})
    def post(self, request):
        password, code = request.data.get("password"), request.data.get("code")
        try:
            validate_security_configuration()
            if not _within_limit(f"admin:reauth:{request.user.pk}", LOGIN_ATTEMPTS_PER_ACCOUNT):
                if cache.add(f"admin:lockout:reauth:{request.user.pk}", 1, LOGIN_WINDOW_SECONDS):
                    record_event(request, "admin_reauthentication_rate_limited", admin=request.user)
                return self.error_response(request, "ADMIN_RATE_LIMITED", "Too many attempts. Try again later.", 429)
        except (ImproperlyConfigured, ConnectionError, TimeoutError, RedisError, ValueError):
            log.warning("admin_reauthentication_dependency_unavailable", extra={"event": "admin_reauthentication_dependency_unavailable",
                         "request_id": str(request.admin_request_id)})
            return self.error_response(request, "ADMIN_AUTH_UNAVAILABLE", "Re-authentication is unavailable.", 503)
        if not (isinstance(password, str) and 1 <= len(password) <= 1024 and isinstance(code, str) and
                len(code) == 6 and code.isascii() and code.isdigit()):
            record_event(request, "admin_reauthentication_failed", admin=request.user)
            return self.error_response(request, "ADMIN_INVALID_CREDENTIALS", "Invalid credentials.", 400)
        now = timezone.now()
        verified = False
        try:
            with transaction.atomic():
                account = AdminAccount.objects.select_for_update().get(pk=request.user.pk)
                session = AdminSession.objects.select_for_update().get(pk=request.auth.pk, admin=account)
                if account.is_active and not session.revoked_at and session.expires_at > now and check_password(password, account.password_hash):
                    counter = matching_totp_counter(decrypt_totp_secret(account.totp_secret_encrypted), code,
                                                    now.timestamp(), account.last_totp_counter)
                    if counter is not None:
                        account.last_totp_counter = counter
                        account.save(update_fields=["last_totp_counter"])
                        session.reauthenticated_at = now
                        session.save(update_fields=["reauthenticated_at"])
                        verified = True
                record_event(request, "admin_reauthenticated" if verified else "admin_reauthentication_failed", admin=account)
        except ImproperlyConfigured:
            return self.error_response(request, "ADMIN_AUTH_UNAVAILABLE", "Re-authentication is unavailable.", 503)
        if not verified:
            return self.error_response(request, "ADMIN_INVALID_CREDENTIALS", "Invalid credentials.", 401)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminOverviewView(AdminAPIView):
    required_permission = Permission.OVERVIEW_READ

    @extend_schema(responses={200: AdminOverviewSerializer, 401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def get(self, request):
        from apps.accounts.models import User
        from apps.bookings.models import Booking
        from apps.rides.models import Ride
        from apps.trust.models import Report

        now = timezone.now()
        local_date = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
        start = datetime.combine(local_date, time.min, tzinfo=ZoneInfo("Asia/Kolkata"))
        end = start + timedelta(days=1)
        return Response({
            "as_of": now.isoformat(),
            "rides_scheduled_today": Ride.objects.filter(status=Ride.Status.OPEN, departure_at__gte=start,
                                                          departure_at__lt=end).count(),
            "rides_next_24_hours": Ride.objects.filter(status=Ride.Status.OPEN, departure_at__gte=now,
                                                         departure_at__lt=now + timedelta(hours=24)).count(),
            "held_seats": Booking.objects.filter(status__in=Booking.HOLDING,
                                                  ride__status=Ride.Status.OPEN, ride__departure_at__gte=now).count(),
            "open_reports": Report.objects.filter(status=Report.Status.OPEN).count(),
            "new_signups_today": User.objects.filter(date_joined__gte=start, date_joined__lt=end).count(),
        })


def _flag_json(flag):
    definition = FLAG_DEFINITIONS[flag.pk]
    return {"key": flag.pk, "description": definition.description, "value": flag.value,
            "default": definition.default, "is_critical": definition.is_critical,
            "updated_at": flag.updated_at, "updated_by": flag.updated_by.name if flag.updated_by else None}


class AdminFeatureFlagListView(AdminAPIView):
    required_permission = Permission.FEATURE_FLAGS_READ

    @extend_schema(responses={200: FeatureFlagSerializer(many=True), 401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def get(self, request):
        flags = FeatureFlag.objects.filter(pk__in=FLAG_DEFINITIONS).select_related("updated_by").order_by("key")
        return Response([_flag_json(flag) for flag in flags])


class AdminFeatureFlagUpdateView(AdminAPIView):
    required_permission = Permission.FEATURE_FLAGS_TOGGLE

    @extend_schema(request=FeatureFlagUpdateSerializer,
                   responses={200: FeatureFlagSerializer, 400: AdminErrorSerializer, 401: AdminErrorSerializer,
                              403: AdminErrorSerializer, 404: AdminErrorSerializer})
    def post(self, request, key):
        if key not in FLAG_DEFINITIONS:
            return self.error_response(request, "ADMIN_FLAG_NOT_FOUND", "This control is not available.", 404)
        value, reason, confirmation = request.data.get("value"), request.data.get("reason"), request.data.get("confirmation")
        if type(value) is not bool or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000 or confirmation != key:
            return self.error_response(request, "ADMIN_FLAG_INVALID", "Enter a valid value, reason and exact control name.", 400)
        now = timezone.now()
        with transaction.atomic():
            account = AdminAccount.objects.select_for_update().get(pk=request.user.pk)
            session = AdminSession.objects.select_for_update().get(pk=request.auth.pk, admin=account)
            if session.revoked_at or session.expires_at <= now or not account.is_active:
                return self.error_response(request, "ADMIN_AUTH_REQUIRED", "Admin session has ended.", 401)
            needed = Permission.FEATURE_FLAGS_TOGGLE_CRITICAL if FLAG_DEFINITIONS[key].is_critical else self.required_permission
            if not has_permission(account.role, needed):
                record_event(request, "permission_denied", admin=account, resource_type="feature_flag")
                return self.error_response(request, "ADMIN_PERMISSION_DENIED", "You do not have permission for this action.", 403)
            if FLAG_DEFINITIONS[key].is_critical and session.reauthenticated_at <= now - timedelta(minutes=10):
                return self.error_response(request, "ADMIN_REAUTH_REQUIRED", "Re-authenticate before changing this control.", 403)
            flag = FeatureFlag.objects.select_for_update().filter(pk=key).first()
            if flag is None:
                return self.error_response(request, "ADMIN_FLAG_NOT_FOUND", "This control is not available.", 404)
            previous = flag.value
            if previous != value:
                flag.value = value
                flag.updated_by = account
                flag.save(update_fields=["value", "updated_by", "updated_at"])
                FeatureFlagChange.objects.create(flag=flag, changed_by=account, old_value=previous,
                                                 new_value=value, reason=redact(reason.strip()))
                record_event(request, "feature_flag_changed", admin=account, resource_type="feature_flag",
                             resource_id=key, before={"value": previous}, after={"value": value}, reason=reason.strip())
                transaction.on_commit(lambda: invalidate_flag(key))
        return Response(_flag_json(flag))


class AdminFeatureFlagHistoryView(AdminAPIView):
    required_permission = Permission.FEATURE_FLAGS_READ

    @extend_schema(responses={200: FeatureFlagChangeSerializer(many=True), 401: AdminErrorSerializer,
                              403: AdminErrorSerializer, 404: AdminErrorSerializer})
    def get(self, request, key):
        if key not in FLAG_DEFINITIONS:
            return self.error_response(request, "ADMIN_FLAG_NOT_FOUND", "This control is not available.", 404)
        can_read_reasons = has_permission(request.user.role, Permission.AUDIT_LOGS_READ)
        changes = FeatureFlagChange.objects.filter(flag_id=key).select_related("changed_by").order_by("-created_at", "-id")[:50]
        return Response([{"id": str(change.pk), "old_value": change.old_value, "new_value": change.new_value,
                          "changed_by": change.changed_by.name,
                          "reason": redact(change.reason) if can_read_reasons else None,
                          "created_at": change.created_at} for change in changes])


class AdminAuditListView(AdminAPIView):
    required_permission = Permission.AUDIT_LOGS_READ

    @extend_schema(parameters=[
        OpenApiParameter("limit", OpenApiTypes.INT, description="Page size from 1 to 100."),
        OpenApiParameter("cursor", OpenApiTypes.STR), OpenApiParameter("action", OpenApiTypes.STR),
        OpenApiParameter("resource_type", OpenApiTypes.STR), OpenApiParameter("resource_id", OpenApiTypes.STR),
        OpenApiParameter("admin_id", OpenApiTypes.UUID), OpenApiParameter("from", OpenApiTypes.DATETIME),
        OpenApiParameter("to", OpenApiTypes.DATETIME),
    ], responses={200: AdminAuditPageSerializer, 400: AdminErrorSerializer,
                  401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def get(self, request):
        query = request.query_params
        try:
            size = int(query.get("limit", "25"))
            if not 1 <= size <= 100:
                raise ValueError("Invalid page size")
            queryset = AdminAuditEvent.objects.select_related("admin").order_by("-created_at", "-id")
            for field in ("action", "resource_type", "resource_id"):
                value = query.get(field)
                if value:
                    if len(value) > 120:
                        raise ValueError("Invalid filter")
                    queryset = queryset.filter(**{field: value})
            if query.get("admin_id"):
                queryset = queryset.filter(admin_id=uuid.UUID(query["admin_id"]))
            for parameter, lookup in (("from", "created_at__gte"), ("to", "created_at__lt")):
                raw = query.get(parameter)
                if raw:
                    parsed = parse_datetime(raw)
                    if parsed is None or timezone.is_naive(parsed):
                        raise ValueError("Invalid datetime")
                    queryset = queryset.filter(**{lookup: parsed})
            if query.get("cursor"):
                cursor = signing.loads(query["cursor"], salt="admin-audit-page", max_age=86400)
                timestamp = parse_datetime(cursor["created_at"])
                identifier = uuid.UUID(cursor["id"])
                if timestamp is None or timezone.is_naive(timestamp):
                    raise ValueError("Invalid cursor")
                queryset = queryset.filter(Q(created_at__lt=timestamp) | Q(created_at=timestamp, id__lt=identifier))
        except (ValueError, KeyError, TypeError, signing.BadSignature):
            return self.error_response(request, "ADMIN_AUDIT_FILTER_INVALID", "Invalid audit filter or cursor.", 400)
        rows = list(queryset[:size + 1])
        has_more = len(rows) > size
        rows = rows[:size]
        next_cursor = None
        if has_more and rows:
            next_cursor = signing.dumps({"created_at": rows[-1].created_at.isoformat(), "id": str(rows[-1].pk)},
                                        salt="admin-audit-page", compress=True)
        return Response({"results": [{"id": str(item.pk), "admin_id": str(item.admin_id) if item.admin_id else None,
                                      "admin_name": item.admin.name if item.admin_id else None,
                                      "admin_role": item.admin_role, "action": item.action,
                                      "resource_type": item.resource_type, "resource_id": item.resource_id,
                                      "before": redact(item.before), "after": redact(item.after), "reason": redact(item.reason),
                                      "request_id": str(item.request_id), "ip_address": item.ip_address,
                                      "user_agent": redact(item.user_agent), "created_at": item.created_at}
                                     for item in rows], "next_cursor": next_cursor})


def _setting_json(key, setting):
    definition = SLA_SETTINGS[key]
    return {"key": key, "value": setting.value if setting else None, "description": definition.description,
            "minimum": definition.minimum, "maximum": definition.maximum,
            "updated_at": setting.updated_at if setting else None}


class AdminSettingsView(AdminAPIView):
    required_permission = Permission.SETTINGS_MANAGE

    @extend_schema(responses={200: PlatformSettingSerializer(many=True), 401: AdminErrorSerializer,
                              403: AdminErrorSerializer})
    def get(self, request):
        settings_by_key = {item.key: item for item in PlatformSetting.objects.filter(pk__in=SLA_SETTINGS)}
        return Response([_setting_json(key, settings_by_key.get(key)) for key in SLA_SETTINGS])


class AdminSettingUpdateView(AdminAPIView):
    required_permission = Permission.SETTINGS_MANAGE

    @extend_schema(request=PlatformSettingUpdateSerializer, responses={200: PlatformSettingSerializer,
                   400: AdminErrorSerializer, 401: AdminErrorSerializer, 403: AdminErrorSerializer})
    def post(self, request, key):
        value, reason = request.data.get("value"), request.data.get("reason")
        if ("value" not in request.data or not validate_setting(key, value) or
                not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000):
            return self.error_response(request, "ADMIN_SETTING_INVALID", "Enter a valid setting and reason.", 400)
        now = timezone.now()
        with transaction.atomic():
            account = AdminAccount.objects.select_for_update().get(pk=request.user.pk)
            session = AdminSession.objects.select_for_update().get(pk=request.auth.pk, admin=account)
            if not account.is_active or session.revoked_at or session.expires_at <= now:
                return self.error_response(request, "ADMIN_AUTH_REQUIRED", "Admin session has ended.", 401)
            if not has_permission(account.role, Permission.SETTINGS_MANAGE):
                record_event(request, "permission_denied", admin=account, resource_type="platform_setting")
                return self.error_response(request, "ADMIN_PERMISSION_DENIED", "You do not have permission for this action.", 403)
            if session.reauthenticated_at <= now - timedelta(minutes=10):
                return self.error_response(request, "ADMIN_REAUTH_REQUIRED", "Re-authenticate before changing this setting.", 403)
            setting, _ = PlatformSetting.objects.select_for_update().get_or_create(key=key, defaults={"value": None})
            previous = setting.value
            if previous != value:
                setting.value = value
                setting.updated_by = account
                setting.save(update_fields=["value", "updated_by", "updated_at"])
                record_event(request, "platform_setting_changed", admin=account, resource_type="platform_setting",
                             resource_id=key, before={"value": previous}, after={"value": value}, reason=reason.strip())
        return Response(_setting_json(key, setting))
