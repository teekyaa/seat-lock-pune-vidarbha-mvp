from django.conf import settings
from django.db import models

from apps.core.codes import short_code


def booking_code():
    return "SL" + short_code(6)


class Booking(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted, awaiting advance"
        ADVANCE_CLAIMED = "advance_claimed", "Advance claimed"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Request expired"
        HOLD_EXPIRED = "hold_expired", "Hold expired"
        CANCELLED_PASSENGER = "cancelled_passenger", "Cancelled by passenger"
        CANCELLED_DRIVER = "cancelled_driver", "Cancelled by driver"
        NO_SHOW = "no_show", "No-show"

    class RefundOutcome(models.TextChoices):
        FULL = "full", "Full refund"
        HALF = "half", "Driver keeps half"
        NONE = "none", "Driver keeps all"
        PENDING_REFILL = "pending_refill", "Decided at departure or refill"

    class PenaltyTier(models.TextChoices):
        HALF = "half", "Driver keeps half"
        ALL = "all", "Driver keeps all"

    # Statuses that take up a seat. See docs/PRODUCTION_PLAN.md decision 1.
    HOLDING = ("accepted", "advance_claimed", "confirmed")
    ACTIVE = ("requested", "accepted", "advance_claimed", "confirmed")

    code = models.CharField(max_length=10, unique=True, default=booking_code, editable=False)
    ride = models.ForeignKey("rides.Ride", on_delete=models.PROTECT, related_name="bookings")
    passenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    policy_version = models.ForeignKey("core.PolicyVersion", on_delete=models.PROTECT, related_name="bookings")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    note = models.CharField(max_length=300, blank=True)

    fare_inr = models.PositiveIntegerField()
    advance_inr = models.PositiveIntegerField()

    passenger_policy_ack_at = models.DateTimeField()
    driver_policy_ack_at = models.DateTimeField(null=True, blank=True)

    request_expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    hold_expires_at = models.DateTimeField(null=True, blank=True)
    advance_claimed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Set when the driver moves departure by more than the tolerance after confirmation.
    free_cancel_any_time = models.BooleanField(default=False)
    at_risk = models.BooleanField(default=False)

    refund_outcome = models.CharField(max_length=16, choices=RefundOutcome.choices, blank=True)
    penalty_tier = models.CharField(max_length=4, choices=PenaltyTier.choices, blank=True)
    refund_inr = models.PositiveIntegerField(null=True, blank=True)
    confirmed_seats_at_cancel = models.PositiveSmallIntegerField(null=True, blank=True)
    refilled_by = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="refilled_booking"
    )
    waitlist_entry = models.OneToOneField(
        "WaitlistEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="booking"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ride", "passenger"],
                condition=models.Q(status__in=["requested", "accepted", "advance_claimed", "confirmed"]),
                name="one_active_booking_per_passenger_ride",
            )
        ]

    def __str__(self):
        return self.code


class Payment(models.Model):
    """A record of what people say happened. The app never holds or moves money (hard rule 1)."""

    class Kind(models.TextChoices):
        ADVANCE = "advance", "Advance"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        CLAIMED = "claimed", "Claimed paid"
        CONFIRMED = "confirmed", "Confirmed received"
        DUE = "due", "Due"
        VOID = "void", "No longer due"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    amount_inr = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices)
    utr = models.CharField(max_length=22, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    # When an unconfirmed refund becomes an open dispute on the driver's record.
    dispute_at = models.DateTimeField(null=True, blank=True, db_index=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    overdue_flagged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class WaitlistEntry(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        OFFERED = "offered", "Seat offered"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        WITHDRAWN = "withdrawn", "Withdrawn"

    ride = models.ForeignKey("rides.Ride", on_delete=models.CASCADE, related_name="waitlist")
    passenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="waitlist_entries")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING, db_index=True)
    offered_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["ride", "passenger"], name="one_waitlist_entry_per_ride")]


class Reconfirmation(models.Model):
    STAGES = (72, 48, 12)

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="reconfirmations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    stage_hours = models.PositiveSmallIntegerField(choices=[(s, f"{s} h") for s in STAGES])
    coming = models.BooleanField()
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["booking", "user", "stage_hours"], name="one_answer_per_stage")]


class TripConfirmation(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="trip_confirmations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    happened = models.BooleanField()
    responded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["booking", "user"], name="one_trip_answer_per_user")]


class NoShowCase(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for passenger"
        DISPUTED = "disputed", "Disputed, with ops"
        UPHELD = "upheld", "No-show stands"
        OVERTURNED = "overturned", "Overturned"

    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name="no_show_case")
    marked_at = models.DateTimeField(auto_now_add=True)
    dispute_until = models.DateTimeField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    disputed_at = models.DateTimeField(null=True, blank=True)
    passenger_statement = models.TextField(blank=True, max_length=1000)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)
