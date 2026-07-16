# Proposal: Preserve Fractional Daily-Bar Volume

## Intent

Real SHARADAR/SEP adjusted volume can be fractional (for example, `48037.936`). Rejecting or coercing it to `int` either blocks historical ingestion or loses financially meaningful source precision. `DailyBar.volume` is therefore a provider-neutral canonical financial value represented as `Decimal`.

## Scope

### In Scope
- Make `DailyBar.volume` a non-negative `Decimal` value supplied by adapters.
- Translate Sharadar, Alpaca, and JSON-fixture volume into the canonical value without rounding or truncation.
- Preserve fractional volume through snapshots and use exact `Decimal` arithmetic for liquidity calculations.
- Cover provider mapping, fixture round trips, and fractional liquidity thresholds.

### Out of Scope
- Changes to OHLC validation, adjustment formulas, screening thresholds, or trading rules.
- New providers, schema migrations for external consumers, or live-execution behavior.
- Further Sharadar context, deduplication, or calendar reconciliation.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sharadar-sep-market-data`: accept fractional SEP volume and preserve it in `DailyBar` without quantization.
- `trading-system`: define canonical daily-bar volume as `Decimal`; Alpaca and fixture snapshot paths must preserve fractional values.
- `sharadar-market-context-generator`: compute adjusted-close × volume liquidity measures with exact `Decimal` arithmetic.

## Approach

Use `Decimal` in the domain contract and at each provider anti-corruption boundary. Pydantic validates non-negative provider values; adapters pass the resulting value unchanged. Snapshots retain integral volume as JSON numbers for compatibility and fractional volume as exact decimal strings. Liquidity calculation multiplies canonical `Decimal` values directly. Sharadar remains backtest-only; paper-first and no-live-before-validation gates are unchanged.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/domain/models.py` | Modified | Canonical volume type |
| `src/invest/adapters/{sharadar_market_data,alpaca_market_data,fixtures_json}.py` | Modified | Provider translation and persistence |
| `src/invest/domain/liquidity_screen.py` | Modified | Exact volume arithmetic |
| `tests/` | Modified | Fractional-volume coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Consumers assume volume is `int` | Medium | Central contract plus adapter/round-trip tests |
| Snapshot representation changes for fractions | Low | Preserve integral JSON numbers; use strings only for fractions |

## Rollback Plan

Revert the domain, all three adapters, liquidity calculation, and tests as one unit; disable Sharadar backtest ingestion because restoring `int` reintroduces fractional SEP rejection or precision loss.

## Dependencies

- Existing Python `Decimal`, Pydantic validation, and provider APIs only.

## Success Criteria

- [x] Canonical and provider volume paths preserve fractional values without quantization.
- [x] Liquidity calculations include the fractional component using only `Decimal` arithmetic.
- [x] Automated coverage exists for Sharadar, Alpaca, fixture round trips, and liquidity boundaries.
- [ ] SDD verification confirms the full suite and a representative SEP pull.
