# Design: Preserve Fractional Daily-Bar Volume

## Technical Approach

Make `DailyBar.volume` the provider-neutral canonical financial quantity as non-negative `Decimal`. Provider adapters (Sharadar SEP, Alpaca bars, JSON fixtures) own raw-payload parsing via Pydantic `Decimal` fields with `ge=0`, then pass the value into `DailyBar` unchanged—no rounding, truncation, or quantization. Snapshot serialization dual-forms integral vs fractional volume for JSON compatibility. Liquidity multiplies `bar.close * bar.volume` with pure `Decimal` arithmetic.

Maps proposal approach and specs for `sharadar-sep-market-data`, `trading-system`, and `sharadar-market-context-generator`. Working tree already contains this implementation; design documents it as-is.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| Canonical volume type | `int` / `float` / `Decimal` | `int` rejects/loses SEP fractions; `float` binary drift; `Decimal` exact | `DailyBar.volume: Decimal` |
| Validation seam | Domain ctor checks / adapter Pydantic | Domain stays pure; adapters already validate OHLC | Pydantic `Field(ge=0)` on adapter payloads; pass through |
| Snapshot encoding | Always string / always number / dual form | Always-string breaks existing integral fixtures; always-number loses fractions | Integral → JSON number (`int`); fractional → exact decimal string |
| Liquidity product | `close * Decimal(volume)` / `close * volume` / float path | Redundant cast after canonical Decimal; float loses precision | Direct `bar.close * bar.volume` |
| Scope of type change | Domain-only vs all three adapters + screen | Partial change leaves broken seams | Domain + Sharadar + Alpaca + fixtures + liquidity |

**Rationale (depth/seams):** Canonical contract is deep and small (`DailyBar.volume: Decimal`). Provider quirks stay at adapter seams (anti-corruption). Domain and liquidity screen never see provider encodings.

## Data Flow

```
SEP/Alpaca/JSON payload
    → Pydantic volume: Decimal (ge=0)
    → DailyBar.volume (unchanged Decimal)
         ├→ SnapshotWriter: integral int | fractional str
         │       → bars.json → JsonFixtureReader → DailyBar.volume
         └→ liquidity_screen: close * volume (Decimal) → median → floor
```

Fail-closed: negative volume → Pydantic `ValidationError` → `MarketDataFetchError("malformed-response")` (live readers) or `FixtureValidationError` (fixtures). No partial bars from a failed page/payload.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/domain/models.py` | Modify | `DailyBar.volume: int` → `Decimal` |
| `src/invest/adapters/sharadar_market_data.py` | Modify | `_SepRow.volume: Decimal = Field(ge=0)`; map `volume=row.volume` |
| `src/invest/adapters/alpaca_market_data.py` | Modify | `_BarPayload.volume: Decimal = Field(ge=0)`; map pass-through; dual-form snapshot write |
| `src/invest/adapters/fixtures_json.py` | Modify | `_BarPayload.volume: Decimal = Field(ge=0)` |
| `src/invest/domain/liquidity_screen.py` | Modify | Drop redundant `Decimal(bar.volume)` cast |
| `tests/adapters/test_sharadar_market_data.py` | Modify | Fractional SEP volume (`250.125`) |
| `tests/adapters/test_alpaca_market_data.py` | Modify | Type assert; integral snapshot number; fractional round-trip |
| `tests/adapters/test_fixtures_json.py` | Modify | Load fractional volume string as `Decimal` |
| `tests/domain/test_liquidity_screen.py` | Modify | Threshold pass using fractional product |

No deletes. No new modules.

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class DailyBar:
    # ...
    volume: Decimal  # non-negative; adapters enforce ge=0

# Snapshot volume (JSON):
#   integral  → int (JSON number)
#   fractional → str exact decimal (e.g. "48037.936")
# Both load via Pydantic Decimal into DailyBar.volume
```

OHLC, adjustment (`closeadj`), pagination, calendars, scanners, and order paths unchanged.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit (adapters) | Fractional SEP/Alpaca/fixture map; negative reject | Existing pytest; extend fixtures with `48037.936` / `250.125` |
| Unit (snapshot) | Integral stays JSON number; fractional string; load equality | `SnapshotWriter` → `JsonFixtureReader` round-trip |
| Unit (liquidity) | Exact `close * volume` at threshold | Screen with floor equal to fractional product |
| Integration/E2E | Out of scope for this change | No new live-provider harness |

RED tests already present in working tree for fractional paths.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No migration required. Dual-form snapshots keep existing integral JSON numbers loadable. No feature flags. Revert domain + three adapters + liquidity + tests as one unit if rolled back; re-enabling `int` would reintroduce fractional SEP rejection/precision loss.

## Open Questions

None — design matches approved boundary and current working-tree implementation.

## Next Step

Ready for tasks (`sdd-tasks`). Handoff this design (with proposal and specs) to the tasks phase for implementation breakdown.
