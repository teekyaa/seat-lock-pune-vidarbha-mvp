from django.conf import settings
from django.db import models

from apps.core.codes import short_code


def ride_code():
    return short_code(6)


class Ride(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CANCELLED = "cancelled", "Cancelled"
        DEPARTED = "departed", "Departed"

    code = models.CharField(max_length=8, unique=True, default=ride_code, editable=False)
    driver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rides")
    vehicle = models.ForeignKey("accounts.Vehicle", on_delete=models.PROTECT, related_name="rides")
    city_pair = models.ForeignKey("core.CityPair", on_delete=models.PROTECT, related_name="rides")
    policy_version = models.ForeignKey("core.PolicyVersion", on_delete=models.PROTECT, related_name="rides")

    departure_at = models.DateTimeField(db_index=True)
    expected_arrival_at = models.DateTimeField()
    original_departure_at = models.DateTimeField()
    pickup_point = models.CharField(max_length=160)
    dropoff_point = models.CharField(max_length=160)
    pickup_details = models.TextField(blank=True)  # Shared only with confirmed passengers

    seats_offered = models.PositiveSmallIntegerField()
    suggested_fare_inr = models.PositiveIntegerField()
    fare_inr = models.PositiveIntegerField()
    advance_inr = models.PositiveIntegerField()
    women_only = models.BooleanField(default=False)
    codriver_wanted = models.BooleanField(default=False)
    notes = models.TextField(blank=True, max_length=500)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["departure_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(seats_offered__gte=1, seats_offered__lte=7), name="ride_seats_1_7"),
            models.CheckConstraint(condition=models.Q(fare_inr__gte=0), name="ride_fare_non_negative"),
        ]

    def __str__(self):
        return f"{self.code} {self.city_pair}"

    @property
    def origin(self):
        return self.city_pair.origin

    @property
    def destination(self):
        return self.city_pair.destination
