"""Pure daily liquidity eligibility screen.

Owns ``ScreenConfig`` (parameterized Core defaults) and the per-day
eligibility decision: inclusive listing status, observed-bar count, current
adjusted close, and trailing-inclusive median dollar volume. No AUM,
ADV-fraction, or price-impact parameters exist on the screen. The screen is
date/Decimal only and never looks ahead past ``as_of``.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Sequence

from invest.domain.models import DailyBar


@dataclass(frozen=True)
class ScreenConfig:
    price_floor: Decimal
    dollar_volume_floor: Decimal
    dollar_volume_window: int
    min_observed_bars: int

    def __post_init__(self) -> None:
        if not self.price_floor.is_finite():
            raise ValueError("price_floor must be finite")
        if not self.dollar_volume_floor.is_finite():
            raise ValueError("dollar_volume_floor must be finite")
        if self.price_floor <= 0:
            raise ValueError("price_floor must be positive")
        if self.dollar_volume_floor <= 0:
            raise ValueError("dollar_volume_floor must be positive")
        if self.dollar_volume_window <= 0:
            raise ValueError("dollar_volume_window must be positive")
        if self.min_observed_bars <= 0:
            raise ValueError("min_observed_bars must be positive")
        if self.min_observed_bars < self.dollar_volume_window:
            raise ValueError("min_observed_bars must be >= dollar_volume_window")

    @classmethod
    def core_defaults(cls) -> "ScreenConfig":
        return cls(
            price_floor=Decimal("10"),
            dollar_volume_floor=Decimal("10_000_000"),
            dollar_volume_window=20,
            min_observed_bars=252,
        )


@dataclass(frozen=True)
class ListingFacts:
    listing_date: date
    delisting_date: date
    primary_common: bool


def screen_eligible(
    bars: Sequence[DailyBar],
    as_of: date,
    listing: ListingFacts,
    config: ScreenConfig,
) -> bool:
    """Evaluate daily liquidity eligibility for ``as_of`` without look-ahead.

    Returns ``True`` only when the listing is an active primary common stock
    on ``as_of`` (inclusive listing through delisting), the observed bar count
    meets ``min_observed_bars``, the current adjusted close meets the price
    floor, and the trailing-inclusive median dollar volume (adjusted close
    times volume) meets the dollar-volume floor. No bar dated after ``as_of``
    participates.
    """
    observed = _observed_bars(bars, as_of)

    if not _is_listing_active(as_of, listing):
        return False

    current = observed[-1] if observed else None
    if current is None or current.date != as_of:
        return False

    if len(observed) < config.min_observed_bars:
        return False

    if current.close < config.price_floor:
        return False

    if _trailing_dollar_volume_median(observed, config.dollar_volume_window) < config.dollar_volume_floor:
        return False

    return True


def _observed_bars(bars: Sequence[DailyBar], as_of: date) -> list[DailyBar]:
    """Bars dated on or before ``as_of``, sorted chronologically (no look-ahead)."""
    return sorted((bar for bar in bars if bar.date <= as_of), key=lambda bar: bar.date)


def _is_listing_active(as_of: date, listing: ListingFacts) -> bool:
    """True when ``as_of`` falls inclusively within the listing interval and the
    listing is a primary common stock."""
    return listing.primary_common and listing.listing_date <= as_of <= listing.delisting_date


def _trailing_dollar_volume_median(observed: list[DailyBar], window: int) -> Decimal:
    """Median of ``adjusted close * volume`` over the trailing ``window`` bars
    (inclusive of the current bar)."""
    trailing = observed[-window:]
    dollar_volumes = [bar.close * bar.volume for bar in trailing]
    return median(dollar_volumes)
