import hmac
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

from apps.core.errors import Conflict, DomainError
from apps.notifications.channels import sms_backend
from apps.trust.services import reliability_for

from .auth import hash_otp, hash_token, issue_token
from .models import AuthToken, OTPChallenge, PushSubscription, User, Vehicle


def normalise_phone(raw):
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
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


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


class OTPRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalise_phone(request.data.get("phone"))
        window = settings.OTP_SEND_WINDOW_SECONDS
        if not _rate_limit(f"otp:phone:{phone}", settings.OTP_SENDS_PER_PHONE, window) or not _rate_limit(
            f"otp:ip:{client_ip(request)}", settings.OTP_SENDS_PER_IP, window
        ):
            return Response(
                {"detail": "Too many codes requested. Please wait 15 minutes and try again.", "code": "rate_limited"},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            OTPChallenge.objects.filter(phone=phone, consumed_at__isnull=True).update(consumed_at=timezone.now())
            OTPChallenge.objects.create(
                phone=phone, code_hash=hash_otp(phone, code),
                expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
            )
        sms_backend().send_otp(phone, code)
        body = {"phone": phone, "expires_in": settings.OTP_TTL_SECONDS}
        if settings.OTP_DEBUG_ECHO:
            body["debug_code"] = code
        return Response(body)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        phone = normalise_phone(request.data.get("phone"))
        code = str(request.data.get("code", "")).strip()
        error = None
        # Errors are raised after the transaction commits, so a wrong attempt is always counted.
        with transaction.atomic():
            challenge = (
                OTPChallenge.objects.select_for_update()
                .filter(phone=phone, consumed_at__isnull=True)
                .order_by("-created_at").first()
            )
            if not challenge or challenge.expires_at <= timezone.now():
                error = DomainError("That code has expired. Ask for a new one.", "otp_expired")
            elif challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
                error = DomainError("Too many wrong tries. Ask for a new code.", "otp_locked")
            else:
                challenge.attempts += 1
                if hmac.compare_digest(challenge.code_hash, hash_otp(phone, code)):
                    challenge.consumed_at = timezone.now()
                else:
                    error = DomainError("That code doesn't match. Check the SMS and try again.", "otp_wrong")
                challenge.save(update_fields=["attempts", "consumed_at"])
            if error is None:
                user, created = User.objects.get_or_create(phone=phone)
                if created:
                    user.set_unusable_password()
                    user.save()
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
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            raise DomainError("That push subscription is incomplete.")
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
        return Response(public_user(user))
