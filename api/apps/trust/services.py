from django.db import connection
from django.utils import timezone

from apps.core.models import Season

from .models import Block, ReliabilityEvent, ReliabilityRecord, Report

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
    return {**ReliabilityRecord.EMPTY, **(record or {})}


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
