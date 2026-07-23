# SEC-8K-UF universe-first PIT mapping audit — I0 result

Issue: [#84](https://github.com/rccarmenaty/invest/issues/84)

## Scope seal

This result corrects the mapping denominator identified by issue #83 without
changing issue #83's terminal `kill_line` or its frozen evidence. It reuses the
exact issue #83 SEC manifest and joins an independently built PIT US
primary-common universe.

- `returns_measured=false`
- `capital_go=false`
- F0 unauthorized and not run
- E1 unauthorized and not run
- No prices, reactions, candles, forward returns, P&L, or outcome-derived
  statistic was fetched, accepted, cached, or computed

## Predecessor evidence

- Issue #83 verdict: `kill_line`
- SEC manifest file SHA-256:
  `66ec5b7365e84ef4e18b667aba0c661109a916859d0f98d6ae7bd511d712a830`
- Issue #83 artifact file SHA-256:
  `62b75b7712d8a608894b0abf07a85f72a511209d64b4cbce280721b428a81a6f`
- Issue #83 artifact self-hash:
  `355ead2c7215e39efe2adde5c57330ccbffe1a7fc06157c6276a157554431c15`

The predecessor hashes and `kill_line` verdict are embedded in the new sealed
universe artifact. This result does not supersede or relabel issue #83.

## Corrected denominator

Issue #83 measured mapping against every original SEC Item 2.02 filer record.
The universe-first audit instead asks two separate questions:

1. Does the independently defined PIT US primary-common universe have adequate
   CIK coverage?
2. Among SEC filer records whose CIK and strictly later known session intersect
   that universe, can at least 95% map to exactly one canonical security?

SEC filer records with no eligible CIK/window intersection remain visible as
out of universe. They are not counted as mapping successes or failures.
Malformed or incomplete identities remain unclassifiable and fail closed.

## Terminal result

**Verdict: `i0_pass`**

**Status: `awaiting_f0_prd`**

| Gate | Result | Evidence |
| --- | ---: | --- |
| I1 reconciliation | PASS | All quarterly source counts agree |
| I2 accession provenance | PASS | 0 duplicate conflicts |
| I3 Item 2.02 semantics | PASS | 409,296 accessions; 417,928 filer records |
| I4 acceptance timestamps | PASS | 417,928 / 417,928 valid (100%) |
| U1 universe CIK coverage | PASS | 15,624 / 15,666 windows (99.7319%) |
| U2 event classification | PASS | 0 unclassifiable original filer records |
| U3 in-universe mapping | PASS | 364,858 / 364,998 candidates (99.9616%) |
| U4 mapping composition | PASS | Worst material year remained below 3× global unmapped rate |
| I7 session calendar | PASS | 0 mapped filings lacked a strictly later regular-session open |
| I8 power basis | PASS | Frozen pre-existing count-only basis present |
| P1 usable years | PASS | 20 usable years versus floor 10 |
| P2 count upper bound | PASS | 362,877 canonical anchors versus 16,125 required |

Source-only counts:

- All original Item 2.02 filer records after amendment handling: 413,636
- In-universe candidates: 364,998
- Exactly mapped candidates: 364,858
- Ambiguous in-universe candidates: 140
- Out-of-universe filer records: 48,638
- Unclassifiable original filer records: 0
- Conservative canonical anchors: 362,877
- Unique mapped issuers: 9,807
- Usable years: 20

The corrected denominator therefore preserves the 95% standard while separating
legitimate non-target SEC filers from actual in-universe identity failures.

## Universe coverage

The universe contains 15,666 date-effective US primary-common listing windows.
Only 42 lack valid CIK coverage.

| Exchange | Windows | With CIK | Rate |
| --- | ---: | ---: | ---: |
| BATS | 4 | 4 | 100% |
| NASDAQ | 10,400 | 10,363 | 99.6442% |
| NYSE | 4,252 | 4,249 | 99.9294% |
| NYSEARCA | 6 | 6 | 100% |
| NYSEMKT | 1,004 | 1,002 | 99.8008% |

## Power basis

The optimistic count-only screen reuses the frozen CFOB Gate-1a basis. It does
not estimate SEC-8K outcome variance.

- Effective dispersion: 0.38
- Primary clustered threshold: 2.5
- 80% power beta quantile: 0.841621
- Target future effect: +1.00%
- Required events: 16,125
- Observed count upper bound: 362,877

Power cannot authorize outcome access. It only establishes that source count is
not the I0 blocker.

## Replay and hashes

The sealed audit replayed byte-identically.

- Universe path:
  `fixtures/real-continuous/reports/sec8k-i0/sec8k-uf-universe.json`
- Universe file SHA-256:
  `b5cc10ede3984a19bd3b18d396ef2ae5476fd7c48364399258e10f9ce6635f37`
- Universe self-hash:
  `1e8eff9ea6831be9e666f8ebed5fc7f3ce5bc77a1261934c75b7e8e10a0f24ec`
- Artifact path:
  `fixtures/real-continuous/reports/sec8k-i0/sec8k-uf-i0-artifact.json`
- Artifact file SHA-256:
  `5e0182decb7a07bd120a7b7c1593340576f042c3e0afb6a13e5b747ac3553787`
- Artifact self-hash:
  `fcdba55f0808b3937b39718e5ae2aa744825ba27d6a27bc37635dd634d02f859`
- Byte-identical replay: PASS

## Stop disposition

This result establishes that the universe-first source and identity contract is
feasible. It does not establish that the named drift hypothesis is true or
false. The line stops at `awaiting_f0_prd`.

No outcome access is authorized by this artifact. Any F0 work requires a new
PRD and explicit human event-only authorization. E1 and capital remain blocked.
