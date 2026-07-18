"""Unit tests for the pure daily liquidity eligibility screen.

Covers ScreenConfig defaults/validation, inclusive listing, observed-bar
count, trailing dollar-volume median, no-look-ahead, and ineligible cases.
No AUM, ADV-fraction, or price-impact parameters exist on the screen.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.liquidity_screen import ListingFacts, ScreenConfig, screen_eligible
from invest.domain.models import DailyBar


def _bar(symbol: str, day: date, close: Decimal, volume: int) -> DailyBar:
    return DailyBar(
        symbol=symbol,
        date=day,
        open=close,
        high=close + Decimal("0.5"),
        low=close - Decimal("0.5"),
        close=close,
        volume=volume,
    )


def _eligible_history(
    symbol: str,
    start: date,
    *,
    close: Decimal = Decimal("50"),
    volume: int = 1_000_000,
    count: int = 252,
) -> tuple[DailyBar, ...]:
    """Build ``count`` daily bars whose dollar volume always satisfies the
    Core $10M floor: close * volume = 50_000_000."""
    return tuple(
        _bar(symbol, start + timedelta(days=i), close, volume) for i in range(count)
    )


# ---------------------------------------------------------------------------
# ScreenConfig defaults
# ---------------------------------------------------------------------------


def test_core_defaults_match_specification() -> None:
    config = ScreenConfig.core_defaults()

    assert config.price_floor == Decimal("10")
    assert config.dollar_volume_floor == Decimal("10_000_000")
    assert config.dollar_volume_window == 20
    assert config.min_observed_bars == 252


# ---------------------------------------------------------------------------
# ScreenConfig finite-positive validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("price_floor", "dollar_volume_floor", "dollar_volume_window", "min_observed_bars"),
    [
        (Decimal("0"), Decimal("10_000_000"), 20, 252),  # zero price floor
        (Decimal("10"), Decimal("0"), 20, 252),  # zero dollar-volume floor
        (Decimal("10"), Decimal("10_000_000"), 0, 252),  # zero volume window
        (Decimal("10"), Decimal("10_000_000"), 20, 0),  # zero min bars
        (Decimal("-1"), Decimal("10_000_000"), 20, 252),  # negative price floor
        (Decimal("10"), Decimal("10_000_000"), 252, 20),  # window exceeds min bars (seasoning)
    ],
)
def test_invalid_config_is_rejected(
    price_floor: Decimal,
    dollar_volume_floor: Decimal,
    dollar_volume_window: int,
    min_observed_bars: int,
) -> None:
    with pytest.raises(ValueError):
        ScreenConfig(
            price_floor=price_floor,
            dollar_volume_floor=dollar_volume_floor,
            dollar_volume_window=dollar_volume_window,
            min_observed_bars=min_observed_bars,
        )


@pytest.mark.parametrize("price_floor", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_non_finite_price_floor_is_rejected(price_floor: Decimal) -> None:
    """NaN and positive/negative Infinity must be rejected, satisfying the
    finite-positive contract -- not merely the positivity check."""
    with pytest.raises(ValueError):
        ScreenConfig(
            price_floor=price_floor,
            dollar_volume_floor=Decimal("10_000_000"),
            dollar_volume_window=20,
            min_observed_bars=252,
        )


@pytest.mark.parametrize(
    "dollar_volume_floor", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_non_finite_dollar_volume_floor_is_rejected(dollar_volume_floor: Decimal) -> None:
    """The dollar-volume floor must likewise reject all non-finite values."""
    with pytest.raises(ValueError):
        ScreenConfig(
            price_floor=Decimal("10"),
            dollar_volume_floor=dollar_volume_floor,
            dollar_volume_window=20,
            min_observed_bars=252,
        )


# ---------------------------------------------------------------------------
# Daily eligibility — Core defaults happy path
# ---------------------------------------------------------------------------


def test_eligible_when_core_defaults_met() -> None:
    """A listed primary common stock with 252 bars whose current price and
    trailing 20-bar median dollar volume meet Core defaults is eligible."""
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(
        listing_date=start,
        delisting_date=as_of + timedelta(days=365),
        primary_common=True,
    )

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is True


def test_eligibility_uses_fractional_volume_in_decimal_dollar_volume() -> None:
    as_of = date(2024, 1, 1)
    close = Decimal("10")
    volume = Decimal("48037.936")
    exact_product = close * volume
    truncated_product = close * Decimal(int(volume))
    bar = DailyBar(
        symbol="ACME",
        date=as_of,
        open=Decimal("10"),
        high=Decimal("11"),
        low=Decimal("9"),
        close=close,
        volume=volume,
    )
    listing = ListingFacts(as_of, as_of, primary_common=True)
    config = ScreenConfig(
        price_floor=Decimal("1"),
        dollar_volume_floor=exact_product,
        dollar_volume_window=1,
        min_observed_bars=1,
    )

    assert exact_product == Decimal("480379.36")
    assert truncated_product < exact_product
    assert screen_eligible((bar,), as_of, listing, config) is True
    assert isinstance(exact_product, Decimal)


# ---------------------------------------------------------------------------
# Daily eligibility — rejection paths (no AUM / ADV / impact)
# ---------------------------------------------------------------------------


def test_ineligible_when_fewer_than_min_observed_bars() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start, count=251)
    as_of = start + timedelta(days=250)
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


def test_ineligible_when_sub_floor_price() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    # Replace the last bar with a sub-$10 close; volume still satisfies the floor.
    bars = bars[:-1] + (_bar("ACME", start + timedelta(days=251), Decimal("9"), 1_000_000),)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


def test_ineligible_when_insufficient_rolling_volume() -> None:
    start = date(2024, 1, 1)
    bars = list(_eligible_history("ACME", start))
    # Last 20 bars have tiny volume so the median dollar volume falls below $10M.
    for i in range(232, 252):
        bars[i] = _bar("ACME", start + timedelta(days=i), Decimal("50"), 100)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


def test_ineligible_when_not_primary_common() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=False)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


# ---------------------------------------------------------------------------
# No look-ahead — later bars never participate
# ---------------------------------------------------------------------------


def test_no_look_ahead_later_bars_do_not_affect_eligibility() -> None:
    """A symbol ineligible on ``as_of`` stays ineligible even when a later
    bar carries enough volume to satisfy the floor — later bars never
    participate in the trailing median."""
    start = date(2024, 1, 1)
    bars = list(_eligible_history("ACME", start))
    # Make the trailing window on as_of fail the floor.
    for i in range(232, 252):
        bars[i] = _bar("ACME", start + timedelta(days=i), Decimal("50"), 100)
    as_of = start + timedelta(days=251)
    # Append a later bar with huge volume — must not rescue eligibility.
    bars.append(_bar("ACME", as_of + timedelta(days=1), Decimal("50"), 10_000_000))
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


def test_no_look_ahead_same_decision_with_or_without_future_bars() -> None:
    """Removing all bars after ``as_of`` yields the same eligibility decision."""
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(start, as_of + timedelta(days=365), primary_common=True)
    config = ScreenConfig.core_defaults()

    with_future = bars + (_bar("ACME", as_of + timedelta(days=5), Decimal("99"), 99_999_999),)
    without_future = bars

    assert screen_eligible(with_future, as_of, listing, config) == screen_eligible(
        without_future, as_of, listing, config
    )


# ---------------------------------------------------------------------------
# Inclusive listing at exact boundaries
# ---------------------------------------------------------------------------


def test_eligible_on_exact_listing_date() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(listing_date=as_of, delisting_date=as_of + timedelta(days=365), primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is True


def test_eligible_on_exact_delisting_date() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(listing_date=start, delisting_date=as_of, primary_common=True)

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is True
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(
        listing_date=as_of + timedelta(days=1),  # not yet listed
        delisting_date=as_of + timedelta(days=365),
        primary_common=True,
    )

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False


def test_ineligible_after_delisting_date() -> None:
    start = date(2024, 1, 1)
    bars = _eligible_history("ACME", start)
    as_of = start + timedelta(days=251)
    listing = ListingFacts(
        listing_date=start,
        delisting_date=as_of - timedelta(days=1),  # already delisted
        primary_common=True,
    )

    assert screen_eligible(bars, as_of, listing, ScreenConfig.core_defaults()) is False
