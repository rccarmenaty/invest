# Proposal: Backtest Warmup vs Replay Window

## Intent

Every real fixture from `invest-generate-context --bars-out` fails replay with `market-context-incomplete` because replay treats warmup bars (fetched before `--start` for indicator/screen history) as decision dates requiring context coverage. Separate the two time ranges: warmup history feeds scanners only; the declared replay window is where completeness, decisions, and portfolio events apply.

## Scope

### In Scope
- Required top-level generation span in the `market-context-v1` artifact (fail-closed: missing/malformed span invalidates the file).
- Replay window defined by the declared span; bars partitioned into pre-window warmup vs in-window replay dates.
- `require_complete` stays fail-closed over the FULL declared window (no shrinking to observed coverage).
- Pre-window bars used only as scanner history — no decisions, entries, exits, validation, or portfolio events before span start.
- Warmup depth guard: Core generation requests >= 253 sessions (scanner `HISTORY_DAYS`), bounded by listing date.
- `--split-date` and CLI range validated against the declared replay window.

### Out of Scope
- Continuous-data pull.
- Dollar-volume-floor changes.
- Strategy/scanner logic changes.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `point-in-time-market-context`: context carries an authoritative generation span; completeness/status remain fail-closed inside it.
- `sharadar-market-context-generator`: span serialization in `market-context-v1`; scanner-sufficient warmup fetch depth (253).
- `trading-system`: backtest replay derives its window from the declared span; warmup bars are history-only; split/range coherence checks.

## Approach

Direction A' from exploration: declare the generation span in the artifact, make replay obey it, keep completeness fail-closed, and guard warmup depth. Design phase MUST resolve these carried-forward decisions (recommendations where evidence is clear):

1. Schema label: required span rejects old v1 files — keep `market-context-v1` or bump version. (Open.)
2. Domain representation: span as first-class field on `MarketContext` — recommended (single domain-owned authority).
3. Post-window bars: deterministic input error — recommended.
4. 253 constant: shared with `MomentumSelectionScanner.HISTORY_DAYS`, not duplicated — recommended.
5. Split semantics: validate against in-window replay dates — recommended; exact-session vs any-in-span remains open.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/domain/market_context.py`, `market_context_builder.py` | Modified | Carry/propagate span; invariants unchanged |
| `src/invest/adapters/backtest_context_json.py` | Modified | Required span schema, strict validation, round-trip |
| `src/invest/application/generate_market_context.py`, `backtest_run.py` | Modified | Retain span; partition warmup/replay dates |
| `src/invest/adapters/sharadar_context_source.py`, `cli.py`, `generate_context_cli.py` | Modified | 253-depth fetch; span/split validation |
| `tests/**` (7 files per exploration) | Modified | Strict TDD coverage |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Strict schema rejects existing v1 artifacts | High (intended) | Regenerate `fixtures/real-years` market-context files |
| `fixtures/backtest-252` goldens drift | High | Update goldens; regression tests for pre-window history |
| Warmup depth increases fetch volume | Low | Bounded by listing date; chunked SEP requests exist |

## Rollback Plan

Single PR off `main`; revert the merge commit. Regenerated fixtures are reproducible via `invest-generate-context`.

## Dependencies

- None external. Fixture regeneration requires Sharadar access (or replay fixtures).

## Success Criteria

- [x] Real generated fixtures with warmup bars replay without `market-context-incomplete`.
- [x] Artifacts without a valid span are rejected fail-closed.
- [x] In-window coverage gaps still raise `MarketContextIncompleteError`.
- [x] No portfolio/decision events dated before the declared span start.
- [x] Core generation requests >= 253 sessions of history.
