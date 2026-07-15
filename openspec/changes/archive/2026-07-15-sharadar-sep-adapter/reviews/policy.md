# Review Policy: sharadar-backtest-source

## Target

The verified PR-2 integration candidate for approved issue #30: backtest-only
Sharadar source selection, CLI behavior, boundary/ignore protections, and
corresponding SDD verification artifacts.

## Risk Classification

- Public CLI source selection and default preservation.
- Backtest-only architecture boundaries.
- Deterministic retry behavior of the activated Sharadar reader.

## Review Rules

- Verify `--source sharadar` is lazy, backtest-only, and default-preserving.
- Verify invalid source failure occurs before reader construction.
- Verify source routing does not activate a wall-clock-dependent code path.
- Only concrete candidate-caused findings may block approval.
