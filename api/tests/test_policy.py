"""Pure policy arithmetic (CLAUDE.md: fares, advance, cancellation tiers)."""
from datetime import datetime, timedelta, timezone

import pytest

from apps.core import policy as calc


class TestSuggestedFare:
    def test_formula_includes_driver_share(self):
        # (710 km x 7 + 1250 tolls) / (3 seats + 1) = 6220 / 4 = 1555
        assert calc.suggested_fare(710, 1250, 3, "7.00") == 1555

    def test_rounds_to_nearest_rupee(self):
        # (100 x 7 + 1) / 2 = 350.5 -> 351 (half up)
        assert calc.suggested_fare(100, 1, 1, 7) == 351

    def test_returns_integer_rupees(self):
        assert isinstance(calc.suggested_fare(333, 17, 2, "6.35"), int)

    def test_rejects_zero_seats(self):
        with pytest.raises(ValueError):
            calc.suggested_fare(100, 0, 0, 7)


class TestFareCap:
    def test_cap_is_15_percent_above(self):
        assert calc.max_fare(1000, 15) == 1150

    def test_cap_rounds_down(self):
        assert calc.max_fare(1555, 15) == 1788  # 1788.25


class TestAdvance:
    @pytest.mark.parametrize(
        "fare,expected",
        [
            (1500, 450),   # 30% = 450 exactly
            (1555, 450),   # 466.5 -> nearest 50 is 450
            (1600, 500),   # 480 -> 500
            (1583, 450),   # 474.9 -> 450
        ],
    )
    def test_thirty_percent_rounded_to_50(self, fare, expected):
        assert calc.advance_for(fare, 30, 50, 300, 1000) == expected

    def test_half_rounds_up_to_next_50(self):
        # 30% of 1250 = 375, exactly halfway between 350 and 400
        assert calc.advance_for(1250, 30, 50, 300, 1000) == 400

    def test_minimum_300(self):
        assert calc.advance_for(800, 30, 50, 300, 1000) == 300

    def test_maximum_1000(self):
        assert calc.advance_for(5000, 30, 50, 300, 1000) == 1000

    def test_never_more_than_fare(self):
        assert calc.advance_for(250, 30, 50, 300, 1000) == 250


class TestCancelTiers:
    @pytest.mark.parametrize(
        "hours,tier",
        [
            (100, calc.FULL),
            (48.01, calc.FULL),
            (48, calc.HALF),      # exactly 48 h is no longer "more than 48 h"
            (30, calc.HALF),
            (12, calc.HALF),      # exactly 12 h is not "under 12 h"
            (11.99, calc.ALL),
            (0.5, calc.ALL),
        ],
    )
    def test_boundaries(self, hours, tier):
        assert calc.passenger_cancel_tier(hours, 48, 12) == tier

    def test_refunds(self):
        assert calc.refund_for_tier(450, calc.FULL) == 450
        assert calc.refund_for_tier(450, calc.HALF) == 225
        assert calc.refund_for_tier(475, calc.HALF) == 238  # driver keeps the rounded-down half (237)
        assert calc.refund_for_tier(450, calc.ALL) == 0

    def test_cutoffs_are_exact_timestamps(self):
        dep = datetime(2026, 11, 7, 15, 30, tzinfo=timezone.utc)
        c = calc.cutoffs(dep, 48, 12)
        assert c.full_refund_until == dep - timedelta(hours=48)
        assert c.full_penalty_from == dep - timedelta(hours=12)
