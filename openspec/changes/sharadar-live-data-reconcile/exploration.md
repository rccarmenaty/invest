# Exploration: sharadar-live-data-reconcile

## Problem

The Sharadar adapters pass synthetic tests but still stop realistic live context generation or make its exported bars unreadable. Three confirmed provider/data-shape conditions are being treated as corruption even though the surrounding payload is valid. The resulting failures either abort the complete multi-page/cohort pull as `malformed-response` or survive export only to be rejected by `JsonFixtureReader`.

The confirmed diagnosis supersedes two stale descriptions in the existing proposal/tasks: blocker 1 is **not** an empty ACTIONS page, and blocker 3 is **not** a raw provider OHLC bad tick. Empty ACTIONS responses remain a separate fail-closed condition; the observed OHLC failures arise only after adjusted-price arithmetic.

## Root Causes

1. **A mapped valued ACTIONS row with exact zero is rejected.** On the diagnosed revision, `SharadarActionsReader._rows_to_actions` rejected valued mapped actions when `value <= 0`. The live row `RVPH`, `2026-02-23`, `dividend=0` is structurally valid and maps to a typed dividend, but exact zero enters the same `malformed-response` path as negative, absent, or non-finite values. The failure occurs inside the full cursor-paginated ACTIONS pull, so no partial event set is returned.

2. **One shared SEP validator conflates strict replay coverage with sparse context observations.** `SharadarMarketDataReader._validate_and_finalize` requires a dense rectangle: every requested symbol must be present, every symbol must have the same date set, and that union must equal every XNYS session in the range. Live SEP is complete at the aggregate session level but legitimately ragged per symbol and per context cohort. `SharadarContextSource._fetch_sep_cohorts` calls this shared `fetch_range`, so one symbol-session gap aborts the cohort and then the whole generator. This evidence does not invalidate the direct replay contract: `invest-backtest --source sharadar` also calls `fetch_range`, and its existing capability promises strict full-universe/full-range coverage. Context generation instead evaluates observed bars (`min_observed_bars`, current-date presence, price, and liquidity), so sparse observations and strict direct replay are distinct semantics currently forced through one validator.

3. **Independent Decimal adjustment creates microscopic OHLC envelope drift.** Raw `_SepRow` values satisfy their OHLC relationships. `_rows_to_bars` then adjusts open, high, and low independently with `raw * (closeadj / close)` while assigning close directly from `closeadj`. Decimal rounding leaves six adjusted rows outside the envelope by exactly `1E-27`. `DailyBar` itself does not validate the envelope, so the rows can be serialized by `BarsFixtureWriter`; `JsonFixtureReader._BarPayload` later rejects them as `fixture-invalid`. The discrepancy is deterministic and introduced by adjustment arithmetic, not by malformed raw prices.

## Live Evidence

- **ACTIONS-only probe:** the first failing mapped row was `RVPH | 2026-02-23 | dividend | 0`. Changing only the exact-zero acceptance condition allowed the complete **612,437-action** live pull to finish. Empty-page handling was unchanged, excluding the empty-ACTIONS diagnosis.
- **Global SEP probe:** **4,196 symbols** and **1,024,219 bars** collectively covered all **256 XNYS sessions**. The abort came from legitimate per-symbol/cohort gaps, not a globally absent session or an empty provider result.
- **Adjusted-envelope probe:** exactly **six** exported bars violated OHLC containment, each by exactly **`1E-27`**. Deterministically restoring low/high containment removed all six discrepancies, after which the same data passed `JsonFixtureReader` validation.
- **Retained artifacts inspected:** `/private/tmp/invest-smoke-integration` preserves the integration reader/validator seams and the RVPH regression case; `/private/tmp/invest-live-checkpoint-global-20260713-20260716/{bars,bars-reconciled}` preserves the unreconciled and reconciled global bar outputs.

## Blast Radius

- **ACTIONS:** any full `SharadarActionsReader.fetch()` can abort on one exact-zero mapped valued row. `SharadarContextSource` fetches ACTIONS once for the candidate universe, so the failure prevents all normalized actions, context blockers, and final context output—not just the affected ticker—from being returned.
- **Context generation:** broad `invest-generate-context` runs are highly exposed because listing-window cohorts contain many symbols with different trading histories. A single legitimate gap aborts its cohort and the entire run before the existing observed-bar liquidity screen can mark the affected date or symbol ineligible.
- **Direct Sharadar replay:** `invest-backtest --source sharadar` shares `fetch_range`, but strict missing-symbol/date coverage is an existing replay safety contract. The live context evidence therefore cannot justify silently weakening direct replay fail-closed behavior.
- **Exported fixture replay:** adjusted envelope drift affects `invest-generate-context --bars-out` artifacts and any later fixture-mode command that loads them through `JsonFixtureReader`. Context derivation may hold the bars in memory, while the persisted fixture pair remains unusable.
- **Unaffected guards:** the probes do not challenge missing required columns, short rows, duplicate `(symbol, date)` rows, blank cursors, non-positive prices, negative/non-finite valued actions, authentication, retry bounds, or pagination limits.

## Open Questions

1. At which contract boundary should strict direct-replay coverage and sparse context-generation observations be represented so that one does not silently change the other?
2. For context generation, should a symbol with some observed bars but session gaps be distinguished from a requested symbol with no rows at all, and what evidence is required to classify either condition safely?
3. The live exact-zero example is a dividend. Is zero valid for every mapped valued ACTIONS kind, including splits, or only for provider kinds demonstrated by live rows?
4. Are the six `1E-27` discrepancies exhaustive only for the retained checkpoint, or do other date ranges produce different counts or Decimal magnitudes?
5. What diagnostic detail must be retained when the public CLI still reports only `malformed-response` or `fixture-invalid`, so future provider reconciles can identify the failing row and stage without another raw-payload probe?
