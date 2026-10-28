import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(r"^\+91[6-9]\d{9}$", "Enter an Indian mobile number like +919876543210.")
upi_validator = RegexValidator(r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z][A-Za-z0-9]{1,64}$", "Enter a UPI ID like name@bank.")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, **extra):
        user = self.model(phone=phone, **extra)
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        user = self.model(phone=phone, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """A member. Signs in with a phone OTP. Staff also have a password for Django admin."""

    class Gender(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"
        OTHER = "other", "Other"
        UNDISCLOSED = "undisclosed", "Prefer not to say"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone = models.CharField(max_length=13, unique=True, validators=[phone_validator])
    name = models.CharField(max_length=80, blank=True)
    hometown = models.CharField(max_length=60, blank=True)
    gender = models.CharField(max_length=12, choices=Gender.choices, default=Gender.UNDISCLOSED)
    college_or_workplace = models.CharField(max_length=120, blank=True)
    photo_url = models.URLField(blank=True)
    email = models.EmailField(blank=True)
    upi_id = models.CharField(max_length=320, blank=True, validators=[upi_validator])

    # Set by staff after verification. Self-declared gender alone never unlocks women-only rides.
    women_only_eligible = models.BooleanField(default=False)

    # ID verification: result, provider and date only. Never the ID number (hard rule 4).
    id_verification_result = models.CharField(
        max_length=10, blank=True, choices=[("passed", "Passed"), ("failed", "Failed")]
    )
    id_verification_provider = models.CharField(max_length=60, blank=True)
    id_verified_on = models.DateField(null=True, blank=True)

    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.name or self.phone

    @property
    def profile_complete(self):
        return bool(self.name and self.hometown and self.terms_accepted_at)


class Vehicle(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="vehicles")
    make_model = models.CharField(max_length=80)
    colour = models.CharField(max_length=30, blank=True)
    registration = models.CharField(max_length=15)  # Private until confirmation (hard rule 3)
    passenger_seats = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.colour} {self.make_model}".strip()


class OTPChallenge(models.Model):
    phone = models.CharField(max_length=13, db_index=True)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuthToken(models.Model):
    """Bearer token. Only the SHA-256 of the token is stored."""

    key_hash = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="auth_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)


class PushSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=1000, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
