# R2-2 results — PEAD F0 data-feasibility

**Date:** 2026-07-21
**Driver:** `fixtures/real-continuous/reports/research_pead_f0.py`
**Artifact:** `fixtures/real-continuous/reports/pead-f0-structure.json`
**Parent PRD:** #69

## Verdict

### **kill_line**

- f2_tape_eligible: `False`
- capital_go: `False` (always false for this line)
- residual claim: **hard frozen** (not reopened)
- returns_measured: `False`
- e1_status: `not_started`

## Source probe

- nasdaq_api_key_present: `False`
- local_sf1_cache: `None`
- sf1_adapter_present: `False`
- live_audit_capable: `False`
- source_label: `no_sf1_or_sec_original_tape`

## Protocol freeze (recorded)

- signal_family: `revenue_confirmed_gaap_earnings_surprise`
- eps_field: `diluted_gaap_eps`
- revenue_field: `gaap_revenue`
- min_prior_seasonal_changes: `8`
- min_annual_test_folds: `10`
- analyst_sue_fallback: `False`
- known_time_policy (evidence): `unknown`

## Coverage

- included: `0`
- rejected: `0`

## Gates

- **D0** [hard] **PASS** — protocol freeze and trial ledger present
- **D1** [hard] **FAIL** — original EPS reconstructability not measured — fail closed
- **D2** [hard] **FAIL** — original revenue reconstructability not measured — fail closed
- **D3** [hard] **FAIL** — known-time policy consistency not measured — fail closed
- **D4** [hard] **FAIL** — integrity not measured (lookahead, current_id_leakage, silent_unit_change, amendment_rewrite) — fail closed
- **D5** [hard] **FAIL** — mapping/terminals not measured — fail closed
- **D6** [hard] **FAIL** — fold floors not measured — fail closed
- **D7** [hard] **FAIL** — stratified reconcile not measured — fail closed

## Pass meaning

Clearing hard data gates ⇒ **F2 immutable-tape PRD eligibility only** — not E1 returns, not capital, not residual unfreeze, not Form-4 auto-start.

## Fail meaning

Publish null / **kill_line** for PEAD under this protocol until a new PRD. Do not add analyst SUE, ranking, guidance NLP, or threshold retuning as rescue.

## How to re-run

```bash
# Fail-closed default when no original-as-published SF1/SEC tape is wired
uv run python fixtures/real-continuous/reports/research_pead_f0.py --write-docs
```

