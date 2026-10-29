from datetime import datetime, time, timedelta

from django.db import connection, transaction
from django.utils import timezone

from apps.core.errors import Conflict, DomainError, Forbidden
from apps.core.models import Season, audit
from apps.core.timefmt import IST, ist
from apps.notifications import services as notify
from .models import Block, ReliabilityEvent, ReliabilityRecord, Report, SeatWanted, Vouch

Kind = ReliabilityEvent.Kind


def record_event(user, kind, *, ride=None, booking=None, hours_before_departure=None, reverses=None, note=""):
    return ReliabilityEvent.objects.create(
        user=user,
        kind=kind,
        ride=ride,
        booking=booking,
        hours_before_departure=hours_before_departure,
        reverses=reverses,
        note=note,
    )


def refresh_reliability_view():
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY trust_reliability_record")


def reliability_for(user):
    """Public record. On PostgreSQL this is at most one scheduler tick old."""
    record = ReliabilityRecord.objects.filter(user_id=user.pk).values(*ReliabilityRecord.EMPTY.keys()).first()
    return {
        **ReliabilityRecord.EMPTY,
        **(record or {}),
        "co_driver_late_cancellations": unreversed(
            ReliabilityEvent.objects.filter(user=user, kind=ReliabilityEvent.Kind.CODRIVER_LATE_CANCEL)
        ).count(),
    }


def unreversed(qs):
    return qs.filter(reversed_by__isnull=True)


def posting_blocked_until(driver, at=None):
    """A second late cancellation inside one festival season blocks posting until the season ends."""
    at = at or timezone.now()
    season = Season.at(at)
    if not season:
        return None
    late = unreversed(
        ReliabilityEvent.objects.filter(
            user=driver,
            kind=Kind.DRIVER_LATE_CANCEL,
            created_at__gte=season.starts_at,
            created_at__lt=season.ends_at,
        )
    ).count()
    return season.ends_at if late >= 2 else None


def is_blocked(a, b):
    return Block.between(a, b)


def block(blocker, blocked):
    if blocker.pk == blocked.pk:
        return None
    obj, _ = Block.objects.get_or_create(blocker=blocker, blocked=blocked)
    return obj


def report(reporter, reported, reason, details="", booking=None):
    return Report.objects.create(
        reporter=reporter, reported=reported, booking=booking, reason=reason, details=details.strip()[:1000]
    )


MAX_ACTIVE_VOUCHES_GIVEN = 5
LATE_CANCELLATIONS = (Kind.PASSENGER_LATE_CANCEL, Kind.DRIVER_LATE_CANCEL, Kind.CODRIVER_LATE_CANCEL)


def vouch_for(voucher, vouchee):
    """Create or reactivate one of a member's five active vouches."""
    if voucher.pk == vouchee.pk:
        raise Conflict("You can't vouch for yourself.")
    if not vouchee.is_active:
        raise Conflict("This member can't receive a vouch right now.")
    if Block.between(voucher, vouchee):
        raise Forbidden("You can't vouch for someone you've blocked or who blocked you.")

    with transaction.atomic():
        # Serialize a member's concurrent vouch requests so the five-vouch limit cannot be crossed.
        voucher = type(voucher).objects.select_for_update().get(pk=voucher.pk)
        existing = Vouch.objects.select_for_update().filter(voucher=voucher, vouchee=vouchee).first()
        if existing and existing.withdrawn_at is None:
            return existing
        active_count = Vouch.objects.filter(voucher=voucher, withdrawn_at__isnull=True).count()
        if active_count >= MAX_ACTIVE_VOUCHES_GIVEN:
            raise Conflict("You can have up to five active vouches. Withdraw one before adding another.", "vouch_limit")
        if existing:
            existing.withdrawn_at = None
            existing.save(update_fields=["withdrawn_at"])
            vouch = existing
            action = "trust.vouch_reactivated"
        else:
            vouch = Vouch.objects.create(voucher=voucher, vouchee=vouchee)
            action = "trust.vouched"
        audit(voucher, action, vouch)
        return vouch


def withdraw_vouch(voucher, vouchee):
    with transaction.atomic():
        voucher = type(voucher).objects.select_for_update().get(pk=voucher.pk)
        vouch = Vouch.objects.select_for_update().filter(
            voucher=voucher, vouchee=vouchee, withdrawn_at__isnull=True
        ).first()
        if not vouch:
            return False
        vouch.withdrawn_at = timezone.now()
        vouch.save(update_fields=["withdrawn_at"])
        audit(voucher, "trust.vouch_withdrawn", vouch)
        return True


def vouch_profile(user, viewer=None):
    received = Vouch.objects.filter(vouchee=user, withdrawn_at__isnull=True).select_related("voucher")
    given = Vouch.objects.filter(voucher=user, withdrawn_at__isnull=True).select_related("vouchee")
    received_data = [
        {"id": str(vouch.voucher_id), "name": vouch.voucher.name, "hometown": vouch.voucher.hometown}
        for vouch in received
    ]
    given_data = []
    for vouch in given:
        late_count = ReliabilityEvent.objects.filter(
            user=vouch.vouchee,
            created_at__gte=vouch.created_at,
            kind__in=LATE_CANCELLATIONS,
            reversed_by__isnull=True,
        ).count()
        given_data.append({
            "id": str(vouch.vouchee_id),
            "name": vouch.vouchee.name,
            "hometown": vouch.vouchee.hometown,
            "late_cancellations_since_vouch": late_count,
        })

    is_authenticated = bool(viewer and viewer.is_authenticated)
    is_self = is_authenticated and viewer.pk == user.pk
    has_vouched = False
    active_given_count = 0
    can_vouch = False
    if is_authenticated:
        has_vouched = Vouch.objects.filter(
            voucher=viewer, vouchee=user, withdrawn_at__isnull=True
        ).exists()
        active_given_count = Vouch.objects.filter(voucher=viewer, withdrawn_at__isnull=True).count()
        can_vouch = not is_self and user.is_active and not Block.between(viewer, user)
    return {
        "received": received_data,
        "given": given_data,
        "viewer": {
            "is_authenticated": is_authenticated,
            "is_self": is_self,
            "has_vouched": has_vouched,
            "can_vouch": can_vouch,
            "active_given_count": active_given_count,
        },
    }


MAX_SEAT_WANTED_FLEX_DAYS = 3


def seat_wanted_matches_ride(wanted, ride, now=None):
    """True when route, open capacity, and IST travel date match the wanted window."""
    from apps.rides.models import Ride
    from apps.rides.services import availability
    from apps.bookings.models import Booking

    now = now or timezone.now()
    if wanted.closed_at or ride.status != Ride.Status.OPEN or ride.departure_at <= now:
        return False
    if wanted.city_pair_id != ride.city_pair_id or wanted.passenger_id == ride.driver_id:
        return False
    if Block.between(wanted.passenger, ride.driver):
        return False
    if Booking.objects.filter(ride=ride, passenger=wanted.passenger, status__in=Booking.HOLDING).exists():
        return False
    ride_date = ride.departure_at.astimezone(IST).date()
    if abs((ride_date - wanted.travel_date).days) > wanted.flex_days:
        return False
    return availability(ride) >= wanted.seats


def alert_matching_seat_wanted(ride):
    """Queue an idempotent in-app/email/push alert for each active matching request."""
    from apps.rides.models import Ride
    from apps.rides.services import availability

    now = timezone.now()
    if ride.status != Ride.Status.OPEN or ride.departure_at <= now:
        return 0
    ride_date = ride.departure_at.astimezone(IST).date()
    requests = SeatWanted.objects.filter(
        city_pair_id=ride.city_pair_id,
        closed_at__isnull=True,
        travel_date__range=(ride_date - timedelta(days=MAX_SEAT_WANTED_FLEX_DAYS),
                            ride_date + timedelta(days=MAX_SEAT_WANTED_FLEX_DAYS)),
    ).select_related("passenger", "city_pair")
    created = 0
    for wanted in requests:
        if not seat_wanted_matches_ride(wanted, ride, now):
            continue
        _schedule_seat_wanted_match(wanted, ride, availability(ride))
        created += 1
    return created


def _schedule_seat_wanted_match(wanted, ride, seats_left):
    route = f"{ride.city_pair.origin} to {ride.city_pair.destination}"
    noun = "seat" if seats_left == 1 else "seats"
    notify.schedule(
        wanted.passenger,
        "seat_wanted_match",
        ride=ride,
        url=notify.ride_url(ride),
        title="A ride matches what you're looking for",
        body=f"A ride is posted {route} for {ist(ride.departure_at)} with {seats_left} {noun} available.",
        dedupe_key=f"seat_wanted:{wanted.pk}:{ride.pk}",
    )


def seat_wanted_notification_relevant(passenger, ride, dedupe_key):
    if ride is None or not dedupe_key:
        return False
    try:
        wanted_id = int(dedupe_key.split(":", 2)[1])
    except (IndexError, ValueError):
        return False
    wanted = SeatWanted.objects.filter(
        pk=wanted_id,
        passenger=passenger,
        city_pair_id=ride.city_pair_id,
        closed_at__isnull=True,
    ).select_related("passenger").first()
    return bool(wanted and seat_wanted_matches_ride(wanted, ride))


def create_seat_wanted(passenger, city_pair, travel_date, seats, flex_days):
    from apps.rides.models import Ride

    if not passenger.profile_complete:
        raise DomainError("Finish your profile before posting a seat-wanted request.", "profile_incomplete")
    if not city_pair.active:
        raise DomainError("That route is not open yet.")
    if travel_date < timezone.localdate(timezone.now(), timezone=IST):
        raise DomainError("Choose today or a future date.")
    if not 1 <= seats <= 7:
        raise DomainError("Choose between 1 and 7 seats.")
    if not 0 <= flex_days <= MAX_SEAT_WANTED_FLEX_DAYS:
        raise DomainError(f"Date flexibility must be between 0 and {MAX_SEAT_WANTED_FLEX_DAYS} days.")

    with transaction.atomic():
        passenger = type(passenger).objects.select_for_update().get(pk=passenger.pk)
        if SeatWanted.objects.filter(
            passenger=passenger, city_pair=city_pair, travel_date=travel_date, closed_at__isnull=True
        ).exists():
            raise Conflict("You already have an active request for this route and date.", "seat_wanted_exists")
        wanted = SeatWanted.objects.create(
            passenger=passenger, city_pair=city_pair, travel_date=travel_date, seats=seats, flex_days=flex_days
        )
        audit(passenger, "seat_wanted.created", wanted, flex_days=flex_days, seats=seats)

    local_start = timezone.make_aware(datetime.combine(travel_date - timedelta(days=flex_days), time.min), IST)
    local_end = timezone.make_aware(datetime.combine(travel_date + timedelta(days=flex_days + 1), time.min), IST)
    rides = Ride.objects.filter(
        city_pair=city_pair, status=Ride.Status.OPEN, departure_at__gte=local_start, departure_at__lt=local_end,
    ).select_related("driver", "vehicle", "city_pair")
    for ride in rides:
        if seat_wanted_matches_ride(wanted, ride):
            from apps.rides.services import availability
            _schedule_seat_wanted_match(wanted, ride, availability(ride))
    return wanted


def close_seat_wanted(wanted, passenger):
    with transaction.atomic():
        wanted = SeatWanted.objects.select_for_update().get(pk=wanted.pk)
        if wanted.passenger_id != passenger.pk:
            raise Forbidden("Only the person who posted this request can close it.")
        if wanted.closed_at is None:
            wanted.closed_at = timezone.now()
            wanted.save(update_fields=["closed_at"])
            audit(passenger, "seat_wanted.closed", wanted)
    return wanted
