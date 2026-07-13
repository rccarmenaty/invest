from invest.domain.rejection import RejectionReason


def test_momentum_selection_scanner_reasons_exist_with_distinct_string_values() -> None:
    assert RejectionReason.NOT_TOP_MOMENTUM_RANK == "not-top-momentum-rank"
    assert RejectionReason.BELOW_52_WEEK_HIGH_PROXIMITY == "below-52-week-high-proximity"
    assert RejectionReason.TREND_FILTER_FAILED == "trend-filter-failed"


def test_momentum_selection_scanner_reasons_are_mutually_distinct() -> None:
    values = {
        RejectionReason.NOT_TOP_MOMENTUM_RANK,
        RejectionReason.BELOW_52_WEEK_HIGH_PROXIMITY,
        RejectionReason.TREND_FILTER_FAILED,
    }

    assert len(values) == 3
