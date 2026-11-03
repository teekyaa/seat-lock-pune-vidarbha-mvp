from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.core import policy as calc
from apps.core.errors import DomainError, Forbidden
from apps.core.models import CityPair, PolicyVersion, audit
from apps.core.timefmt import ist
from apps.trust.services import alert_matching_seat_wanted, posting_blocked_until

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


def advance_for(fare_inr, policy, required=True):
    """Percentage of the fare with no floor or ceiling; zero when the driver switched it off (spec D6)."""
    if not required:
        return 0
    return calc.advance_percent_only(fare_inr, policy.advance_percent, policy.advance_round_to_inr)


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


def _check_driver(driver, vehicle, departure_at, seats_offered, women_only, policy_ack, advance_required, now, policy):
    if not driver.profile_complete:
        raise DomainError("Finish your profile before posting a ride.", "profile_incomplete")
    if not policy_ack:
        raise DomainError("Please agree to the cancellation policy to post.", "policy_ack_required")
    if advance_required and not driver.upi_id:
        raise DomainError("Add your UPI ID so passengers can pay the advance.", "upi_required")
    if vehicle.owner_id != driver.pk:
        raise Forbidden("That car is not on your profile.")
    blocked_until = posting_blocked_until(driver, now)
    if blocked_until:
        raise Forbidden(
            f"You cancelled late twice this season, so posting is paused until {ist(blocked_until)}.", "posting_blocked"
        )
    if departure_at < now + timedelta(hours=policy.min_post_lead_hours):
        raise DomainError(f"Departure must be at least {policy.min_post_lead_hours} hours from now.")
    if not 1 <= seats_offered <= min(7, vehicle.passenger_seats):
        raise DomainError(f"Seats must be between 1 and {min(7, vehicle.passenger_seats)} for this car.")
    if women_only and not driver.women_only_eligible:
        raise Forbidden("Women-only rides need a verified profile. Ask us to verify you.", "women_only_ineligible")


def _check_fare(fare_inr, max_fare_inr):
    if fare_inr < 0:
        raise DomainError("Enter a fare in rupees.")
    if fare_inr > max_fare_inr:
        raise DomainError(
            f"Fares stay cost-sharing. The most you can ask for this trip is Rs {max_fare_inr} a seat.",
            "fare_above_cap",
        )


def create_ride(driver, *, city_pair, vehicle, departure_at, seats_offered, fare_inr, pickup_point, dropoff_point,
                pickup_details="", notes="", women_only=False, codriver_wanted=False, duration_hours=None, policy_ack=False,
                advance_required=True):
    """Legacy fixed city-pair ride. New rides use create_route_ride."""
    now = timezone.now()
    policy = PolicyVersion.current(now)
    _check_driver(driver, vehicle, departure_at, seats_offered, women_only, policy_ack, advance_required, now, policy)
    if not pickup_point.strip() or not dropoff_point.strip():
        raise DomainError("Add a pickup and drop-off point.")
    if not city_pair.active:
        raise DomainError("That route is not open yet.")
    quote = fare_quote(city_pair, seats_offered, policy)
    _check_fare(fare_inr, quote["max_fare_inr"])
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
        advance_inr=advance_for(fare_inr, policy, advance_required),
        advance_required=advance_required,
        women_only=women_only,
        codriver_wanted=codriver_wanted,
        notes=notes.strip(),
    )
    audit(driver, "ride.created", ride, fare_inr=fare_inr, suggested=quote["suggested_fare_inr"])
    alert_matching_seat_wanted(ride)
    return ride


def create_route_ride(driver, *, route, from_place, to_place, vehicle, departure_at, seats_offered, fare_inr,
                      pickup, dropoff_point, disabled_stop_ids=(), pickup_details="", notes="", women_only=False,
                      codriver_wanted=False, duration_hours=None, policy_ack=False, advance_required=True):
    """Post a ride on a verified route. The fare is checked per leg against the 15% cap (hard rule 2),
    and the stops, distance and tolls it was priced on are copied onto the ride."""
    from apps.routes import services as routes

    now = timezone.now()
    policy = PolicyVersion.current(now)
    _check_driver(driver, vehicle, departure_at, seats_offered, women_only, policy_ack, advance_required, now, policy)
    if not route.active:
        raise DomainError("That route is not open yet.")
    pickup = pickup or {}
    pickup_name = " ".join(str(pickup.get("name", "")).split())[:160]
    if not pickup_name or not dropoff_point.strip():
        raise DomainError("Add an exact pickup point and a drop-off point.")
    seg = routes.segment(route, from_place, to_place)
    disabled = {int(x) for x in disabled_stop_ids}
    if {from_place.pk, to_place.pk} & disabled:
        raise DomainError("The start and end of your trip are always stops.")
    quote = routes.quote(route, from_place, to_place, seats_offered, policy)
    _check_fare(fare_inr, quote["max_fare_inr"])
    if seg.minutes:
        expected_arrival = departure_at + timedelta(minutes=seg.minutes)
    else:
        duration = duration_hours or 12
        if not 1 <= duration <= 24:
            raise DomainError("Trip duration must be between 1 and 24 hours.")
        expected_arrival = departure_at + timedelta(hours=duration)

    ride = Ride.objects.create(
        driver=driver,
        vehicle=vehicle,
        route=route,
        from_place=from_place,
        to_place=to_place,
        city_pair=CityPair.objects.filter(origin__iexact=from_place.name, destination__iexact=to_place.name).first(),
        stops=[{**routes.stop_json(s), "enabled": s.place.pk not in disabled} for s in seg.stops],
        distance_km=seg.distance_km,
        tolls_inr=seg.tolls_inr,
        policy_version=policy,
        departure_at=departure_at,
        original_departure_at=departure_at,
        expected_arrival_at=expected_arrival,
        pickup_point=pickup_name,
        pickup_address=str(pickup.get("address", "")).strip()[:300],
        pickup_eloc=str(pickup.get("eloc", "")).strip()[:12],
        dropoff_point=dropoff_point.strip()[:160],
        pickup_details=pickup_details.strip(),
        seats_offered=seats_offered,
        suggested_fare_inr=quote["suggested_fare_inr"],
        fare_inr=fare_inr,
        advance_inr=advance_for(fare_inr, policy, advance_required),
        advance_required=advance_required,
        women_only=women_only,
        codriver_wanted=codriver_wanted,
        notes=notes.strip(),
    )
    audit(driver, "ride.created", ride, fare_inr=fare_inr, suggested=quote["suggested_fare_inr"], route=route.slug)
    alert_matching_seat_wanted(ride)
    return ride


def search(origin=None, destination=None, date=None, viewer=None):
    from apps.trust.models import Block

    qs = Ride.objects.filter(status=Ride.Status.OPEN, departure_at__gt=timezone.now()).select_related(
        "driver", "vehicle", "city_pair", "from_place", "to_place", "route"
    )
    # Phase 1 matches the ride's own start and end. Stops along the way come in Phase 2.
    if origin:
        qs = qs.filter(Q(from_place__name__iexact=origin) | Q(from_place__isnull=True, city_pair__origin__iexact=origin))
    if destination:
        qs = qs.filter(Q(to_place__name__iexact=destination) |
                       Q(to_place__isnull=True, city_pair__destination__iexact=destination))
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
