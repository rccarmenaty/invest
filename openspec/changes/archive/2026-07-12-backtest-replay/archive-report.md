# Archive Report: backtest-replay

## Scope

Backtest/replay harness validating day-0 momentum mechanics — fills the SPEC-mandated gap identified when `paper-trading-execution` was archived: replay/backtest expectancy proof must precede paper trading ("a system that skips phases 1-3 is a donation to the market"), but this project built paper execution first. This change retrofits the validation phase.

Three named decisions carried through spec and design:
- **Day-0-only mechanics**: the harness measures exactly what `paper-trading-execution` already runs live, explicitly labeled in every report as NOT SPEC's confirmed-entry thesis.
- **Survivorship-biased universe**: uses a fixed historical liquid-universe screen, loudly disclaimed as not point-in-time index membership.
- **Gap-trading strategy**: explicitly rejected as out of scope, enforced by a structural test.

## Delivery

- **PR #17** (size:exception, ~1,000 authored lines, all 27 tasks) — implemented by a Claude Sonnet 5 subagent. First change in this project with **no Codex involvement at all** (Codex was retired mid-session in favor of Claude-agents-only).
- **PR #18** (correction) — fixed 2 CRITICAL 4R findings via a Claude Sonnet subagent: an evadable boundary test strengthened against module-then-attribute import evasion; a silent-incomplete-backtest gap closed by failing closed with `symbol-missing-at-fetch` on the live `fetch_range` path.

## Review

Two lineages:

- **backtest-replay** (full 4R over the merged implementation): 11 findings — `BRISK-001` (boundary test claiming "never touches BrokerPort" was evadable via `from invest.adapters import alpaca_broker` + attribute access) and `BRES-001` (silent incomplete backtest indistinguishable from a legitimate zero-signal result, undermining the report's trustworthiness for a go/no-live decision), both CRITICAL and corrected via PR #18, plus 9 info rows.
- **backtest-replay-clean** (terminal lineage over the corrected tree): 6 info rows, receipt **approved**.

## Verify

PASS — 9/9 requirements, 159 tests passed (3 expected credential-gated skips), ruff clean. Harness confirmed: synthetic fixture produces `trade_count: 3` with all three literal disclaimer strings verbatim; live-range path without credentials fails closed correctly; `invest-scan` regression unaffected.

## Open Follow-ups (non-blocking)

- Out-of-scope guard is a filename-substring grep (`"gap"`/`"confirmation"` in module name), not AST-based — evadable by renaming a forbidden-logic module.
- `malformed-response` conflates real schema failures with simply hitting the `MAX_PAGES` cap during a large fetch, obscuring root-cause diagnosis.
- `scan_decisions` rescans the entire merged bar window from scratch per trading day — O(days × total_bars), unguarded for real multi-year multi-symbol backtests.
- **Recurring pattern, now flagged in THREE consecutive review cycles**: `ExitReason`/`GateReason`-style StrEnums exist but production code sometimes uses raw literal strings instead (decorative enum, no type-system backing); the four CLI entrypoints (`main`/`fetch_main`/`execute_main`/`backtest_main`) emit two incompatible failure-record JSON shapes for the same exception types. Recommend a dedicated cleanup slice — this has survived correction passes in `paper-trading-execution` and `backtest-replay` without being addressed because each review scoped fixes to CRITICAL/BLOCKER findings only.
