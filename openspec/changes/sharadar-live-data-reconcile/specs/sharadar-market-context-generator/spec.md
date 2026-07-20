# Delta for Sharadar Market Context Generator

## Purpose

Allow structurally valid sparse SEP cohorts to reach the existing eligibility screen while requiring complete aggregate XNYS session evidence across all cohort requests.

## MODIFIED Requirements

### Requirement: Complete safe MarketContext decisions

The generator SHALL emit `MarketContext`-compatible coverage, eligibility, and blocker windows. `SharadarContextSource` MUST explicitly request context-only sparse SEP observations for cohort retrieval. Per-symbol and per-cohort missing sessions that satisfy the sparse-observation contract MUST NOT abort generation or be treated as structurally incomplete input; affected symbols and dates MUST be evaluated by the existing observed-bar, current-date, price, and liquidity rules, and failures of those rules MUST produce `eligible=false`, not a blocker.

Before building context decisions, `SharadarContextSource` MUST compute the union of expected XNYS sessions across all cohort request ranges and the union of returned SEP dates across all cohort results. Those unions MUST be equal. A missing expected session in the global returned-date union, an unexpected returned date, a requested symbol with no observations, or structurally invalid TICKERS, SEP, or ACTIONS data MUST fail closed and MUST produce no context file. ACTIONS MUST create only effective-date `corporate-action` blockers, omit them on ineligible dates, and never emit `earnings-context-missing`.

(Previously: each cohort inherited strict dense SEP validation, so a legitimate per-symbol or per-cohort session gap aborted the complete generation run before aggregate coverage and eligibility could be evaluated.)

#### Scenario: Encode a corporate action safely

- GIVEN an eligible symbol with one or more ACTIONS events on a covered date
- WHEN context is built
- THEN that date MUST be blocked as `corporate-action` without overlapping windows

#### Scenario: Ragged cohorts with complete global session evidence proceed

- GIVEN structurally valid cohort results where every requested symbol has at least one observation, individual symbols and cohorts omit sessions, and the global returned-date union equals the global expected-XNYS-session union
- WHEN `SharadarContextSource` validates all cohort results
- THEN generation MUST proceed without requiring dense per-symbol or per-cohort coverage
- AND each sparse symbol and date MUST be classified by the existing eligibility screen
- AND insufficient observed history or missing current-date evidence MUST produce `eligible=false` rather than abort the run

#### Scenario: Globally missing expected session fails closed

- GIVEN structurally valid sparse cohort results whose global returned-date union omits at least one session from the global expected-XNYS-session union
- WHEN `SharadarContextSource` performs aggregate validation
- THEN generation MUST fail before context decisions are built
- AND no context file MAY be written

#### Scenario: Refuse structurally invalid context input

- GIVEN a requested candidate has structurally invalid TICKERS, SEP, or ACTIONS data, or has no SEP observation in its requested cohort
- WHEN input validation runs
- THEN generation MUST fail closed
- AND no context file MAY be written
