"""The route network: places, measured road legs, and named routes made of ordered stops.

Distances and tolls live on legs and are verified by the team before a route can be used
(docs/ROUTE_NETWORK_SPEC.md, D3 and D4). Rides copy the figures they were priced on, so a
later correction never changes an existing ride's fare.
"""
from django.conf import settings
from django.db import models


class Place(models.Model):
    class Region(models.TextChoices):
        WEST = "west", "Pune and western Maharashtra"
        MARATHWADA = "marathwada", "Marathwada"
        VIDARBHA = "vidarbha", "Vidarbha"

    name = models.CharField(max_length=60, unique=True)
    aliases = models.CharField(max_length=200, blank=True, help_text="Other names, comma separated.")
    region = models.CharField(max_length=12, choices=Region.choices)
    lat = models.DecimalField(max_digits=9, decimal_places=6)
    lng = models.DecimalField(max_digits=9, decimal_places=6)
    mappls_eloc = models.CharField(max_length=12, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Leg(models.Model):
    """A directional road segment between two neighbouring places."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Entered by the team"
        MAPPLS = "mappls", "Measured with Mappls"
        DEMO = "demo", "Synthetic demo figure"

    from_place = models.ForeignKey(Place, on_delete=models.PROTECT, related_name="legs_out")
    to_place = models.ForeignKey(Place, on_delete=models.PROTECT, related_name="legs_in")
    distance_km = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    tolls_inr = models.PositiveIntegerField(null=True, blank=True)
    typical_minutes = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.MANUAL)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["from_place__name", "to_place__name"]
        constraints = [
            models.UniqueConstraint(fields=["from_place", "to_place"], name="one_leg_per_direction"),
            models.CheckConstraint(condition=~models.Q(from_place=models.F("to_place")), name="leg_not_a_loop"),
        ]

    def __str__(self):
        return f"{self.from_place} to {self.to_place}"

    @property
    def measured(self):
        return self.distance_km is not None and self.tolls_inr is not None

    def ready(self):
        """Usable for pricing: measured, verified, and never demo data outside development."""
        if not self.measured or self.verified_at is None:
            return False
        return settings.DEBUG or self.source != self.Source.DEMO


class Route(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    place = models.ForeignKey(Place, on_delete=models.PROTECT, related_name="route_stops")
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["route", "position"]
        constraints = [
            models.UniqueConstraint(fields=["route", "position"], name="one_stop_per_position"),
            models.UniqueConstraint(fields=["route", "place"], name="place_once_per_route"),
        ]

    def __str__(self):
        return f"{self.route}: {self.position}. {self.place}"
