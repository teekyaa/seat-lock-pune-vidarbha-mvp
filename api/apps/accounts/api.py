import hmac
import logging
import re
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errors import Conflict, DomainError, Forbidden, ServiceUnavailable
from apps.core.timefmt import ist
from apps.notifications.channels import SMSDeliveryError
from apps.admin_dashboard.flags import is_enabled
from apps.trust.services import reliability_for, vouch_profile

from . import abuse, otp
from .auth import hash_otp, hash_token, issue_token
from .models import AuthToken, OTPAbuseFlag, OTPChallenge, PushSubscription, User, Vehicle

log = logging.getLogger(__name__)


def normalise_phone(raw):
    if not isinstance(raw, str):
        raise DomainError("Enter a 10 digit Indian mobile number.", "invalid_phone")
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 10:
        digits = "91" + digits
    phone = "+" + digits
    if not re.fullmatch(r"\+91[6-9]\d{9}", phone):
        raise DomainError("Enter a 10 digit Indian mobile number.", "invalid_phone")
    return phone


def _rate_limit(key, limit, window):
    """Fixed-window counter in the cache (Redis in production)."""
    cache.add(key, 0, window)  # starts the window only if the key is new
    return cache.incr(key) <= limit


def client_ip(request):
    remote = request.META.get("REMOTE_ADDR", "")
    if remote in settings.OTP_TRUSTED_PROXY_IPS:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        return forwarded.split(",")[0].strip() or remote
    return remote


class MeSerializer(serializers.ModelSerializer):
    accept_terms = serializers.BooleanField(write_only=True, required=False)
    profile_complete = serializers.BooleanField(read_only=True)
    id_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "phone", "name", "hometown", "gender", "college_or_workplace", "photo_url", "email", "upi_id",
            "women_only_eligible", "id_verified", "terms_accepted_at", "profile_complete", "accept_terms", "date_joined",
        ]
        read_only_fields = ["id", "phone", "women_only_eligible", "terms_accepted_at", "date_joined"]

    def get_id_verified(self, user):
        return user.id_verification_result == "passed"

    def update(self, instance, validated):
        if validated.pop("accept_terms", False) and not instance.terms_accepted_at:
            instance.terms_accepted_at = timezone.now()
        return super().update(instance, validated)


def public_user(user):
    return {
        "id": str(user.pk),
        "name": user.name,
        "hometown": user.hometown,
        "photo_url": user.photo_url,
        "member_since": user.date_joined.date().isoformat(),
        "id_verified": user.id_verification_result == "passed",
        "women_only_verified": user.women_only_eligible,
        "reliability": reliability_for(user),
    }


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ["id", "make_model", "colour", "registration", "passenger_seats"]

    def validate_passenger_seats(self, value):
        if not 1 <= value <= 7:
            raise serializers.ValidationError("Between 1 and 7 passenger seats.")
        return value

    def validate_registration(self, value):
        value = re.sub(r"[\s-]", "", value).upper()
        if not re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}", value):
            raise serializers.ValidationError("Enter a registration like MH12AB1234.")
        return value


def _too_many(detail, code, retry_after=None, **extra):
    body = {"detail": detail, "code": code, **extra}
    if retry_after is not None:
        body["retry_after"] = max(1, int(retry_after))
    return Response(body, status=status.HTTP_429_TOO_MANY_REQUESTS)


def _blocked_response(kind, until):
    who = "this number" if kind == OTPAbuseFlag.Kind.PHONE else "your network"
    return _too_many(
        f"Too many code requests from {who}. You can try again after {ist(until)}.",
        "otp_blocked", retry_after=(until - timezone.now()).total_seconds(), blocked_until=until.isoformat(),
    )


def _limit_hit(kind, value, reason, detail, code="rate_limited"):
    """Record the hit (may start a block), then refuse. The hit is committed before responding."""
    flag = abuse.record_hit(kind, value, reason, timezone.now())
    if flag.blocked_until and flag.blocked_until > timezone.now():
        return _blocked_response(kind, flag.blocked_until)
    return _too_many(detail, code)


class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalise_phone(request.data.get("phone"))
        prefer = "sms" if request.data.get("channel") == "sms" else None
        ip = client_ip(request)
        now = timezone.now()
        phone_key, ip_key = abuse.subject_key(phone), abuse.subject_key(ip)
        Kind = OTPAbuseFlag.Kind

        for kind, value in ((Kind.PHONE, phone), (Kind.IP, ip)):
            until = abuse.active_block(kind, value, now)
            if until:
                return _blocked_response(kind, until)

        window, day = settings.OTP_SEND_WINDOW_SECONDS, 24 * 3600
        wait = "Too many codes requested. Please wait 15 minutes and try again."
        if not _rate_limit(f"otp:phone:{phone_key}", settings.OTP_SENDS_PER_PHONE, window):
            return _limit_hit(Kind.PHONE, phone, "phone_burst", wait)
        if not _rate_limit(f"otp:phone:day:{phone_key}", settings.OTP_SENDS_PER_PHONE_DAY, day):
            return _limit_hit(Kind.PHONE, phone, "phone_daily",
                              "Too many codes requested today. Please try again tomorrow.")
        if not _rate_limit(f"otp:ip:{ip_key}", settings.OTP_SENDS_PER_IP, window):
            return _limit_hit(Kind.IP, ip, "ip_burst", wait)
        if not _rate_limit(f"otp:ip:day:{ip_key}", settings.OTP_SENDS_PER_IP_DAY, day):
            return _limit_hit(Kind.IP, ip, "ip_daily", "Too many codes requested from your network today.")
        # One device asking codes for many different numbers looks like SMS pumping or enumeration.
        if cache.add(f"otp:ipnum:{ip_key}:{phone_key}", 1, day):
            cache.add(f"otp:ipnums:{ip_key}", 0, day)
            if cache.incr(f"otp:ipnums:{ip_key}") > settings.OTP_NUMBERS_PER_IP_DAY:
                return _limit_hit(Kind.IP, ip, "ip_many_numbers",
                                  "Too many different numbers from your network today. Please try again tomorrow.")

        # Escalating wait between codes for the same number: 60 s, then 2 min, then 5 min.
        sent_key = f"otp:sent:hour:{phone_key}"
        steps = settings.OTP_RESEND_COOLDOWN_STEPS
        cooldown = steps[min(cache.get(sent_key, 0), len(steps) - 1)]
        cooldown_key = f"otp:cooldown:{phone}"
        if not cache.add(cooldown_key, now.timestamp() + cooldown, cooldown):
            ends = cache.get(cooldown_key) or now.timestamp()
            retry = max(1, int(ends - now.timestamp()))
            abuse.record_hit(Kind.PHONE, phone, "cooldown_ignored", now)
            return _too_many(f"Please wait {retry} seconds before requesting another code.", "otp_cooldown",
                             retry_after=retry)

        # Spend cap across everyone, so a bot army cannot run up the SMS bill.
        if not _rate_limit("otp:global:hour", settings.OTP_GLOBAL_SENDS_PER_HOUR, 3600):
            cache.delete(cooldown_key)
            log.error("OTP global hourly send cap reached; refusing new codes.")
            raise ServiceUnavailable("We're getting a lot of sign-ins right now. Please try again in a few minutes.",
                                     "otp_busy")

        code = f"{secrets.randbelow(1_000_000):06d}"
        try:
            delivery = otp.deliver(phone, code, prefer)
        except SMSDeliveryError:
            cache.delete(cooldown_key)
            raise ServiceUnavailable("We couldn't send a code right now. Please try again.", "sms_unavailable") from None
        with transaction.atomic():
            challenge = OTPChallenge.objects.create(
                phone=phone, code_hash="" if delivery.verifies_code else hash_otp(phone, code),
                channel=delivery.channel, backend=delivery.backend, provider_ref=delivery.reference,
                expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS),
            )
            OTPChallenge.objects.filter(phone=phone, consumed_at__isnull=True).exclude(pk=challenge.pk).update(
                consumed_at=now
            )
        cache.add(sent_key, 0, 3600)
        cache.incr(sent_key)
        body = {"phone": phone, "expires_in": settings.OTP_TTL_SECONDS, "resend_after": cooldown,
                "channel": delivery.channel, "sms_available": otp.sms_available()}
        if settings.OTP_DEBUG_ECHO and not delivery.verifies_code:
            body["debug_code"] = code
        return Response(body)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ip = client_ip(request)
        if not _rate_limit(f"otp:verify:ip:{abuse.subject_key(ip)}", settings.OTP_VERIFY_ATTEMPTS_PER_IP,
                           settings.OTP_VERIFY_WINDOW_SECONDS):
            return _limit_hit(OTPAbuseFlag.Kind.IP, ip, "verify_burst",
                              "Too many verification attempts. Please try again later.")
        phone = normalise_phone(request.data.get("phone"))
        code = str(request.data.get("code", "")).strip()
        error = None
        locked_now = False
        # Errors are raised after the transaction commits, so a wrong attempt is always counted.
        with transaction.atomic():
            challenge = (
                OTPChallenge.objects.select_for_update()
                .filter(phone=phone, consumed_at__isnull=True)
                .order_by("-created_at", "-pk").first()
            )
            if not challenge or challenge.expires_at <= timezone.now():
                error = DomainError("That code has expired. Ask for a new one.", "otp_expired")
            elif challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
                error = DomainError("Too many wrong tries. Ask for a new code.", "otp_locked")
            else:
                challenge.attempts += 1
                if not re.fullmatch(r"\d{4,8}", code):
                    result = "wrong"
                elif challenge.code_hash:
                    result = "ok" if hmac.compare_digest(challenge.code_hash, hash_otp(phone, code)) else "wrong"
                else:
                    try:
                        result = otp.provider_check(challenge.backend, challenge.provider_ref, code)
                    except SMSDeliveryError:
                        result = "unavailable"
                if result == "ok":
                    challenge.consumed_at = timezone.now()
                elif result == "expired":
                    challenge.consumed_at = timezone.now()
                    error = DomainError("That code has expired. Ask for a new one.", "otp_expired")
                elif result == "unavailable":
                    challenge.attempts -= 1  # the provider failed, not the user
                    error = ServiceUnavailable("We couldn't check the code right now. Please try again.",
                                               "otp_check_unavailable")
                else:
                    error = DomainError("That code doesn't match. Check the message and try again.", "otp_wrong")
                    locked_now = challenge.attempts >= settings.OTP_MAX_ATTEMPTS
                challenge.save(update_fields=["attempts", "consumed_at"])
            if error is None:
                user = User.objects.filter(phone=phone).first()
                if user is None and not is_enabled("signup.new_signups_enabled"):
                    error = ServiceUnavailable("New registrations are temporarily unavailable.", "signup_paused")
                else:
                    user, created = User.objects.get_or_create(phone=phone)
                    if created:
                        user.set_unusable_password()
                        user.save()
        if locked_now:
            abuse.record_hit(OTPAbuseFlag.Kind.PHONE, phone, "wrong_codes", timezone.now())
        if error:
            raise error
        if not user.is_active:
            raise DomainError("This account is suspended. Contact support.", "suspended")
        return Response({"token": issue_token(user), "is_new": created, "user": MeSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        AuthToken.objects.filter(key_hash=hash_token(header.removeprefix("Bearer ").strip())).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        s = MeSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class VehicleListView(APIView):
    def get(self, request):
        return Response(VehicleSerializer(request.user.vehicles.all(), many=True).data)

    def post(self, request):
        s = VehicleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save(owner=request.user)
        return Response(s.data, status=status.HTTP_201_CREATED)


class VehicleDetailView(APIView):
    def delete(self, request, pk):
        vehicle = request.user.vehicles.filter(pk=pk).first()
        if not vehicle:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            vehicle.delete()
        except ProtectedError:
            raise Conflict("This car is on a ride, so it can't be removed.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class PushKeyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"public_key": settings.VAPID_PUBLIC_KEY})


class PushSubscriptionView(APIView):
    def post(self, request):
        keys = request.data.get("keys") or {}
        endpoint = request.data.get("endpoint")
        from apps.notifications.channels import valid_push_endpoint
        if not isinstance(keys, dict) or not valid_push_endpoint(endpoint) or not keys.get("p256dh") or not keys.get("auth"):
            raise DomainError("That push subscription is incomplete.")
        if PushSubscription.objects.filter(endpoint=endpoint).exclude(user=request.user).exists():
            raise Forbidden("That push subscription belongs to another account.")
        PushSubscription.objects.update_or_create(
            endpoint=endpoint, defaults={"user": request.user, "p256dh": keys["p256dh"], "auth": keys["auth"]}
        )
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, request):
        PushSubscription.objects.filter(user=request.user, endpoint=request.data.get("endpoint")).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicProfileView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        user = User.objects.filter(pk=pk, is_active=True).first()
        if not user:
            return Response(status=status.HTTP_404_NOT_FOUND)
        data = public_user(user)
        data["vouches"] = vouch_profile(user, request.user)
        return Response(data)
