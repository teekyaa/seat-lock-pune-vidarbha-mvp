"""Pure policy arithmetic. No database access, so every rule is easy to test.

All money is integer rupees (hard rule 7).
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

FULL = "full"
HALF = "half"
ALL = "all"


def _round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def suggested_fare(distance_km: int, tolls_inr: int, seats_offered: int, fuel_cost_per_km) -> int:
    """(distance x fuel cost per km + tolls) / (seats offered + 1), rounded to the nearest rupee.

    The +1 is the driver's own share of the trip cost.
    """
    if seats_offered < 1:
        raise ValueError("seats_offered must be at least 1")
    total = Decimal(distance_km) * Decimal(str(fuel_cost_per_km)) + Decimal(tolls_inr)
    return _round_half_up(total / Decimal(seats_offered + 1))


def max_fare(suggested: int, cap_percent: int) -> int:
    """The highest fare a driver may set: at most cap_percent above the suggestion, rounded down."""
    return (suggested * (100 + cap_percent)) // 100


def advance_for(fare_inr: int, percent: int, round_to: int, minimum: int, maximum: int) -> int:
    """percent of fare, rounded to the nearest round_to, clamped to [minimum, maximum].

    Never more than the fare itself.
    """
    raw = Decimal(fare_inr) * Decimal(percent) / Decimal(100)
    rounded = _round_half_up(raw / Decimal(round_to)) * round_to
    return min(fare_inr, max(minimum, min(maximum, rounded)))


def passenger_cancel_tier(hours_before_departure: float, full_refund_before: int, full_penalty_under: int) -> str:
    """Which tier a confirmed passenger cancellation falls into.

    More than 48 h: full refund. 48 h down to 12 h, both inclusive: driver keeps half.
    Under 12 h: driver keeps all.
    """
    if hours_before_departure > full_refund_before:
        return FULL
    if hours_before_departure >= full_penalty_under:
        return HALF
    return ALL


def refund_for_tier(advance_inr: int, tier: str) -> int:
    """Refund owed to the passenger. For HALF the driver keeps the rounded-down half."""
    if tier == FULL:
        return advance_inr
    if tier == HALF:
        return advance_inr - advance_inr // 2
    return 0


@dataclass(frozen=True)
class Cutoffs:
    full_refund_until: object  # last moment a cancellation still gets a full refund (exclusive)
    full_penalty_from: object  # from this moment on, the driver keeps all


def cutoffs(departure_at, full_refund_before: int, full_penalty_under: int) -> Cutoffs:
    return Cutoffs(
        full_refund_until=departure_at - timedelta(hours=full_refund_before),
        full_penalty_from=departure_at - timedelta(hours=full_penalty_under),
    )
