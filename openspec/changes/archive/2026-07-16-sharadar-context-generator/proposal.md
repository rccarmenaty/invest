# Proposal: Sharadar Market Context Generator

## Intent

The shipped TICKERS/ACTIONS adapters expose point-in-time reference data but have no lawful caller. Add a standalone, backtest-only generator that discovers a broad US candidate set, combines TICKERS, SEP bars, and ACTIONS into daily eligibility/corporate-action context, and writes `market-context-v1` JSON for later replay.

## Scope

### In Scope
- Broad TICKERS discovery; SEP retrieval for candidates; daily context derivation; deterministic JSON output.
- Configurable Core momentum defaults: price ≥ $10; median 20-bar dollar volume ≥ $10M; 252 observed bars; primary common stocks on AMEX/ARCA/NASDAQ/NYSE. These are research-grounded capacity heuristics, not legal or universal truths.
- Explicitly opt the generator into `_ALLOWED_REFERENCE_READER_CALLERS` and amend the canonical backtest-only reference-data boundary.
- Mocked-network tests and 2–3 chained PR-sized implementation slices because forecast work exceeds 400 changed lines.

### Out of Scope
- Running replay/backtests; live, paper, broker, execution, or scanner changes.
- Live external calls in tests; AUM-aware ADV-fraction/price-impact enforcement.
- SEP reader refactoring or transport deduplication unless separately justified as strictly necessary.

## Proposal Question Round

Approved defaults and boundaries above are settled. Nonblocking decisions remain: future AUM/capacity profile adjustment; dual-class/ADR exchange-category policy; optional survivor-count cap; optional rolling-ADV metadata. Defaults remain parameters, so these do not block proposal.

## Capabilities

### New Capabilities
- `sharadar-market-context-generator`: broad discovery through validated `market-context-v1` generation.

### Modified Capabilities
- `trading-system`: permit one explicit backtest-only reference-reader caller and generator route while preserving default-deny isolation elsewhere.

## Approach

Create a standalone generation flow that consumes existing reader contracts, computes point-in-time daily decisions without AUM inputs, and writes the schema already consumed by `BacktestContextJsonReader`. It must never invoke `BacktestRun`.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/domain/` | New | Pure screening/context derivation |
| `src/invest/adapters/`, `pyproject.toml` | New/Modified | Writer and standalone entrypoint |
| `tests/`, `tests/test_boundaries.py` | Modified | Mocked contracts and deliberate allowlist |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Broad SEP volume | High | Bound/fail closed; size in design |
| Boundary leakage | High | Explicit allowlist and canonical delta |
| Heuristics overstate capacity | Med | Parameterize; defer AUM controls |

## Rollback Plan

Remove the generator, entrypoint, tests, allowlist entry, and boundary delta; existing adapters, replay, and JSON reader remain unchanged.

## Dependencies

- Shipped Sharadar TICKERS, ACTIONS, SEP adapters and existing `market-context-v1` consumer.

## Success Criteria

- [ ] Broad inputs produce deterministic, point-in-time JSON without invoking replay.
- [ ] Defaults are configurable and tests perform no live calls.
- [ ] Only the opted-in backtest generator can construct reference readers.
