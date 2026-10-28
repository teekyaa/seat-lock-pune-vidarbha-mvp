from django.conf import settings
from django.db import models


class CityPair(models.Model):
    """One direction of a corridor route. Distance and tolls feed the fare formula (hard rule 2)."""

    origin = models.CharField(max_length=40)
    destination = models.CharField(max_length=40)
    distance_km = models.PositiveIntegerField()
    tolls_inr = models.PositiveIntegerField()
    typical_duration_hours = models.PositiveSmallIntegerField(default=12)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["origin", "destination"], name="unique_city_pair")]
        ordering = ["origin", "destination"]

    def __str__(self):
        return f"{self.origin} to {self.destination}"


class PolicyVersion(models.Model):
    """Immutable snapshot of fare and cancellation rules. Bookings keep the version they were made under."""

    label = models.CharField(max_length=40, unique=True)
    effective_from = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Fare (hard rule 2)
    fuel_cost_per_km = models.DecimalField(max_digits=6, decimal_places=2)
    fare_cap_percent = models.PositiveSmallIntegerField(default=15)

    # Advance
    advance_percent = models.PositiveSmallIntegerField(default=30)
    advance_round_to_inr = models.PositiveIntegerField(default=50)
    advance_min_inr = models.PositiveIntegerField(default=300)
    advance_max_inr = models.PositiveIntegerField(default=1000)
    hold_hours = models.PositiveSmallIntegerField(default=2)

    # Cancellation tiers
    full_refund_before_hours = models.PositiveSmallIntegerField(default=48)
    full_penalty_under_hours = models.PositiveSmallIntegerField(default=12)
    refund_due_hours = models.PositiveSmallIntegerField(default=24)
    driver_late_cancel_hours = models.PositiveSmallIntegerField(default=48)
    reschedule_tolerance_hours = models.PositiveSmallIntegerField(default=2)

    # No-show and disputes
    no_show_after_minutes = models.PositiveSmallIntegerField(default=30)
    no_show_dispute_hours = models.PositiveSmallIntegerField(default=24)
    refund_dispute_after_hours = models.PositiveSmallIntegerField(default=24)

    # Requests and waitlist
    min_post_lead_hours = models.PositiveSmallIntegerField(default=6)
    request_close_hours = models.PositiveSmallIntegerField(default=12)
    request_ttl_hours = models.PositiveSmallIntegerField(default=12)
    waitlist_offer_minutes = models.PositiveSmallIntegerField(default=120)
    waitlist_offer_short_minutes = models.PositiveSmallIntegerField(default=30)

    summary = models.TextField(help_text="Plain-language policy shown to both people at booking time.")

    class Meta:
        ordering = ["-effective_from"]

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        if self.pk and self.bookings.exists():
            raise ValueError("A policy version in use by bookings cannot be changed. Create a new version.")
        super().save(*args, **kwargs)

    @classmethod
    def current(cls, at=None):
        from django.utils import timezone

        at = at or timezone.now()
        policy = cls.objects.filter(effective_from__lte=at).order_by("-effective_from").first()
        if policy is None:
            raise LookupError("No policy version is in effect. Run `manage.py seed_reference_data`.")
        return policy


class Season(models.Model):
    """Festival season. A second late cancellation by a driver inside one season blocks posting until it ends."""

    name = models.CharField(max_length=60)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return self.name

    @classmethod
    def at(cls, moment):
        return cls.objects.filter(starts_at__lte=moment, ends_at__gt=moment).first()


class AuditLog(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


def audit(actor, action, obj, **data):
    AuditLog.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
        data=data,
    )
