"""Only expose flags with behavior actually enforced by the application."""
import logging
from dataclasses import dataclass

from django.db import DatabaseError
from django.core.cache import cache
from redis.exceptions import RedisError

from .models import FeatureFlag

log = logging.getLogger("seatlock.admin")


@dataclass(frozen=True)
class FlagDefinition:
    description: str
    default: bool
    is_critical: bool


FLAG_DEFINITIONS = {
    "rides.new_ride_creation_enabled": FlagDefinition("Allow drivers to post new rides.", True, True),
    "bookings.new_bookings_enabled": FlagDefinition("Allow new booking requests and waitlist acceptance.", True, True),
    "signup.new_signups_enabled": FlagDefinition("Allow new user registrations.", True, False),
}


def is_enabled(key: str) -> bool:
    """Read critical controls from the database; cache noncritical controls briefly."""
    definition = FLAG_DEFINITIONS[key]
    cache_key = f"admin:feature_flag:{key}"
    if not definition.is_critical:
        try:
            cached = cache.get(cache_key)
            if type(cached) is bool:
                return cached
        except (RedisError, ConnectionError, TimeoutError, ValueError):
            log.warning("feature_flag_cache_unavailable", extra={"event": "feature_flag_cache_unavailable", "context": {"flag_key": key}})
    try:
        value = FeatureFlag.objects.filter(pk=key).values_list("value", flat=True).first()
    except DatabaseError:
        log.warning("feature_flag_database_unavailable", extra={"event": "feature_flag_database_unavailable", "context": {"flag_key": key}})
        return definition.default
    if value is None:
        log.warning("feature_flag_missing", extra={"event": "feature_flag_missing", "context": {"flag_key": key}})
        return definition.default
    if not definition.is_critical:
        try:
            cache.set(cache_key, value, timeout=30)
        except (RedisError, ConnectionError, TimeoutError, ValueError):
            log.warning("feature_flag_cache_unavailable", extra={"event": "feature_flag_cache_unavailable", "context": {"flag_key": key}})
    return value


def invalidate_flag(key: str) -> None:
    try:
        cache.delete(f"admin:feature_flag:{key}")
    except (RedisError, ConnectionError, TimeoutError, ValueError):
        log.warning("feature_flag_cache_unavailable", extra={"event": "feature_flag_cache_unavailable", "context": {"flag_key": key}})
