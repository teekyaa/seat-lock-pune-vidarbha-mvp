from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.core import policy as calc
from apps.core.errors import DomainError, Forbidden
from apps.core.models import CityPair, PolicyVersion, audit
from apps.core.timefmt import ist
from apps.trust.services import posting_blocked_until

from .models import Ride

HOLDING = ("accepted", "advance_claimed", "confirmed")


def fare_quote(city_pair: CityPair, seats_offered: int, policy: PolicyVersion | None = None):
    policy = policy or PolicyVersion.current()
    suggested = calc.suggested_fare(city_pair.distance_km, city_pair.tolls_inr, seats_offered, policy.fuel_cost_per_km)
    return {
        "city_pair_id": city_pair.pk,
        "distance_km": city_pair.distance_km,
        "tolls_inr": city_pair.tolls_inr,
        "fuel_cost_per_km": str(policy.fuel_cost_per_km),
        "seats_offered": seats_offered,
        "suggested_fare_inr": suggested,
        "max_fare_inr": calc.max_fare(suggested, policy.fare_cap_percent),
        "advance_inr": advance_for(suggested, policy),
        "policy_version": policy.label,
    }


def advance_for(fare_inr, policy):
    return calc.advance_for(
        fare_inr, policy.advance_percent, policy.advance_round_to_inr, policy.advance_min_inr, policy.advance_max_inr
    )


def availability(ride: Ride):
    """Seats left after holds and open waitlist offers. Holds reserve a seat (plan decision 1)."""
    now = timezone.now()
    held = ride.bookings.filter(status__in=HOLDING).count()
    offers = ride.waitlist.filter(status="offered", offer_expires_at__gt=now).count()
    return max(0, ride.seats_offered - held - offers)


def with_seat_counts(qs):
    now = timezone.now()
    return qs.annotate(
        seats_held=Count("bookings", filter=Q(bookings__status__in=HOLDING), distinct=True),
        offers_open=Count(
            "waitlist", filter=Q(waitlist__status="offered", waitlist__offer_expires_at__gt=now), distinct=True
        ),
    )


def create_ride(driver, *, city_pair, vehicle, departure_at, seats_offered, fare_inr, pickup_point, dropoff_point,
                pickup_details="", notes="", women_only=False, duration_hours=None, policy_ack=False):
    now = timezone.now()
    policy = PolicyVersion.current(now)
    if not driver.profile_complete:
        raise DomainError("Finish your profile before posting a ride.", "profile_incomplete")
    if not policy_ack:
        raise DomainError("Please agree to the cancellation policy to post.", "policy_ack_required")
    if not driver.upi_id:
        raise DomainError("Add your UPI ID so passengers can pay the advance.", "upi_required")
    if vehicle.owner_id != driver.pk:
        raise Forbidden("That car is not on your profile.")
    blocked_until = posting_blocked_until(driver, now)
    if blocked_until:
        raise Forbidden(
            f"You cancelled late twice this season, so posting is paused until {ist(blocked_until)}.", "posting_blocked"
        )
    if not pickup_point.strip() or not dropoff_point.strip():
        raise DomainError("Add a pickup and drop-off point.")
    if not city_pair.active:
        raise DomainError("That route is not open yet.")
    if departure_at < now + timedelta(hours=policy.min_post_lead_hours):
        raise DomainError(f"Departure must be at least {policy.min_post_lead_hours} hours from now.")
    if not 1 <= seats_offered <= min(7, vehicle.passenger_seats):
        raise DomainError(f"Seats must be between 1 and {min(7, vehicle.passenger_seats)} for this car.")
    if women_only and not driver.women_only_eligible:
        raise Forbidden("Women-only rides need a verified profile. Ask us to verify you.", "women_only_ineligible")

    quote = fare_quote(city_pair, seats_offered, policy)
    if fare_inr < 0:
        raise DomainError("Enter a fare in rupees.")
    if fare_inr > quote["max_fare_inr"]:
        raise DomainError(
            f"Fares stay cost-sharing. The most you can ask for this trip is Rs {quote['max_fare_inr']} a seat.",
            "fare_above_cap",
        )
    duration = duration_hours or city_pair.typical_duration_hours
    if not 1 <= duration <= 24:
        raise DomainError("Trip duration must be between 1 and 24 hours.")

    ride = Ride.objects.create(
        driver=driver,
        vehicle=vehicle,
        city_pair=city_pair,
        policy_version=policy,
        departure_at=departure_at,
        original_departure_at=departure_at,
        expected_arrival_at=departure_at + timedelta(hours=duration),
        pickup_point=pickup_point.strip(),
        dropoff_point=dropoff_point.strip(),
        pickup_details=pickup_details.strip(),
        seats_offered=seats_offered,
        suggested_fare_inr=quote["suggested_fare_inr"],
        fare_inr=fare_inr,
        advance_inr=advance_for(fare_inr, policy),
        women_only=women_only,
        notes=notes.strip(),
    )
    audit(driver, "ride.created", ride, fare_inr=fare_inr, suggested=quote["suggested_fare_inr"])
    return ride


def search(origin=None, destination=None, date=None, viewer=None):
    from apps.trust.models import Block

    qs = Ride.objects.filter(status=Ride.Status.OPEN, departure_at__gt=timezone.now()).select_related(
        "driver", "vehicle", "city_pair"
    )
    if origin:
        qs = qs.filter(city_pair__origin__iexact=origin)
    if destination:
        qs = qs.filter(city_pair__destination__iexact=destination)
    if date:
        from datetime import datetime, time

        from apps.core.timefmt import IST

        start = datetime.combine(date, time.min, tzinfo=IST)
        qs = qs.filter(departure_at__gte=start, departure_at__lt=start + timedelta(days=1))
    if viewer is not None:
        blocked = Block.objects.filter(Q(blocker=viewer) | Q(blocked=viewer)).values_list("blocker_id", "blocked_id")
        hidden = {uid for pair in blocked for uid in pair} - {viewer.pk}
        qs = qs.exclude(driver_id__in=hidden)
    return with_seat_counts(qs).order_by("departure_at")
