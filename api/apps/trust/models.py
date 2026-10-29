from django.conf import settings
from django.db import models


class ReliabilityEvent(models.Model):
    """Append-only. A correction is a new event that points at the one it reverses."""

    class Kind(models.TextChoices):
        TRIP_COMPLETED = "trip_completed", "Trip completed"
        PASSENGER_EARLY_CANCEL = "passenger_early_cancel", "Passenger cancelled early"
        PASSENGER_LATE_CANCEL = "passenger_late_cancel", "Passenger cancelled late"
        CODRIVER_LATE_CANCEL = "codriver_late_cancel", "Co-driver cancelled late"
        DRIVER_EARLY_CANCEL = "driver_early_cancel", "Driver cancelled early"
        DRIVER_LATE_CANCEL = "driver_late_cancel", "Driver cancelled late"
        DRIVER_CHANGE = "driver_change", "Driver moved departure"
        NO_SHOW = "no_show", "No-show"
        REFUND_OVERDUE = "refund_overdue", "Refund overdue"
        REFUND_RESOLVED = "refund_resolved", "Overdue refund confirmed"
        CORRECTION = "correction", "Correction"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reliability_events")
    kind = models.CharField(max_length=24, choices=Kind.choices)
    ride = models.ForeignKey("rides.Ride", null=True, blank=True, on_delete=models.PROTECT)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.PROTECT)
    hours_before_departure = models.FloatField(null=True, blank=True)
    reverses = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversed_by"
    )
    note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Reliability events are append-only. Record a correction instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Reliability events are append-only. Record a correction instead.")


class ReliabilityRecord(models.Model):
    """Read-only public record: a materialised view over reliability_events (see migration 0002)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.DO_NOTHING, related_name="+", db_column="user_id"
    )
    completed_trips = models.IntegerField()
    passenger_early_cancellations = models.IntegerField()
    passenger_late_cancellations = models.IntegerField()
    driver_early_cancellations = models.IntegerField()
    driver_late_cancellations = models.IntegerField()
    driver_changes = models.IntegerField()
    no_shows = models.IntegerField()
    open_refund_disputes = models.IntegerField()

    class Meta:
        managed = False
        db_table = "trust_reliability_record"

    EMPTY = {
        "completed_trips": 0,
        "passenger_early_cancellations": 0,
        "passenger_late_cancellations": 0,
        "driver_early_cancellations": 0,
        "driver_late_cancellations": 0,
        "driver_changes": 0,
        "no_shows": 0,
        "open_refund_disputes": 0,
    }


class Report(models.Model):
    class Reason(models.TextChoices):
        UNSAFE_DRIVING = "unsafe_driving", "Unsafe driving"
        HARASSMENT = "harassment", "Harassment"
        MISLEADING_RIDE = "misleading_ride", "Ride not as described"
        PAYMENT_DISPUTE = "payment_dispute", "Payment problem"
        NO_SHOW = "no_show", "No-show"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_made")
    reported = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_received")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.PROTECT)
    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True, max_length=1000)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    ops_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class Block(models.Model):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block"),
            models.CheckConstraint(condition=~models.Q(blocker=models.F("blocked")), name="no_self_block"),
        ]

    @classmethod
    def between(cls, a, b):
        return cls.objects.filter(models.Q(blocker=a, blocked=b) | models.Q(blocker=b, blocked=a)).exists()


class Vouch(models.Model):
    """Should-have (US-24). Schema only for now."""

    voucher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vouches_given")
    vouchee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vouches_received")
    created_at = models.DateTimeField(auto_now_add=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["voucher", "vouchee"], name="unique_vouch")]


class SeatWanted(models.Model):
    """A passenger's requested corridor and date window for US-23 ride alerts."""

    passenger = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="seat_wanted")
    city_pair = models.ForeignKey("core.CityPair", on_delete=models.CASCADE)
    travel_date = models.DateField()
    seats = models.PositiveSmallIntegerField(default=1)
    flex_days = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["passenger", "city_pair", "travel_date"],
                condition=models.Q(closed_at__isnull=True),
                name="one_active_seat_wanted_per_day",
            )
        ]
