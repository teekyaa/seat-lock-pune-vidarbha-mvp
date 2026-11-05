"""Flag and temporarily block phone numbers and IPs that keep hitting OTP limits.

Every limit hit is recorded on an OTPAbuseFlag row (one per phone or IP). Hits inside
OTP_FLAG_WINDOW_HOURS add up; reaching the threshold blocks code requests for a while. Repeat
offenders are blocked for longer. Each write commits on its own, so the hit is kept even though the
request is then refused (CLAUDE.md: never raise after saving a state you want kept).
"""
import hashlib
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import OTPAbuseFlag

log = logging.getLogger(__name__)


def subject_key(value):
    """Short hash for cache keys, so raw phone numbers and IPs are not used as Redis key names."""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{value}".encode()).hexdigest()[:24]


def active_block(kind, value, now):
    """The block end time if this subject is blocked right now, else None."""
    return (OTPAbuseFlag.objects.filter(kind=kind, value=value, blocked_until__gt=now)
            .values_list("blocked_until", flat=True).first())


def _block_length(kind, times_blocked):
    base = settings.OTP_BLOCK_HOURS_PHONE if kind == OTPAbuseFlag.Kind.PHONE else settings.OTP_BLOCK_HOURS_IP
    # Each repeat doubles the block, capped at a week.
    return timedelta(hours=min(base * (2 ** times_blocked), 24 * 7))


def record_hit(kind, value, reason, now):
    """Count one limit hit. Returns the flag row. Blocks the subject when the threshold is reached."""
    window = timedelta(hours=settings.OTP_FLAG_WINDOW_HOURS)
    threshold = settings.OTP_BLOCK_AFTER_HITS
    for _ in range(2):  # retry once if two requests create the row at the same moment
        try:
            with transaction.atomic():
                flag = OTPAbuseFlag.objects.select_for_update().filter(kind=kind, value=value).first()
                if flag is None:
                    flag = OTPAbuseFlag.objects.create(kind=kind, value=value, reason=reason,
                                                       first_seen=now, last_seen=now)
                if now - flag.last_seen > window:
                    flag.hits = 0  # quiet for a full window: start counting again
                flag.hits += 1
                flag.total_hits += 1
                flag.reason = reason
                flag.last_seen = now
                if flag.hits >= threshold and not (flag.blocked_until and flag.blocked_until > now):
                    flag.blocked_until = now + _block_length(kind, flag.times_blocked)
                    flag.times_blocked += 1
                    flag.hits = 0
                    flag.reviewed_at = None
                    log.warning("OTP abuse block: %s blocked until %s (%s)", kind, flag.blocked_until, reason)
                flag.save()
                return flag
        except IntegrityError:
            continue
    raise RuntimeError("Could not record the OTP limit hit.")
