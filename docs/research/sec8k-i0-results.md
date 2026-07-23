# SEC-8K-2.02 timestamped source audit — I0 result

Issue: [#83](https://github.com/rccarmenaty/invest/issues/83)

## Scope seal

This result is source-feasibility evidence only. The run accepted SEC filing metadata,
accession/CIK identities, acceptance timestamps, PIT listing facts, exchange sessions,
counts, and the pre-existing count-only power basis.

- `returns_measured=false`
- `capital_go=false`
- F0 unauthorized and not run
- E1 unauthorized and not run
- No prices, reactions, candles, forward returns, P&L, or return-derived SEC-8K
  statistic were fetched, accepted, cached, or computed

## Source snapshot

The final acquisition used the SEC's nightly bulk Submissions API archive plus all 88
compressed quarterly master indexes for 2004–2025. The bulk archive was processed
without extraction.

- Bulk source: `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip`
- Bulk snapshot date: 2026-07-22
- Bulk bytes: 1,552,873,228
- Bulk SHA-256: `177ad76e6ca6cd4f5f39e19cccea76c289e7f19ca20846666225ec6604a85799`
- Manifest generated at: `2026-07-22T21:31:27Z`
- Full population: 1,768,050 unique 8-K/8-K/A accessions
- Joint-filer structure: 1,817,636 accession × CIK records and 34,893
  multi-CIK accessions
- Item 2.02 population: 409,296 unique accessions and 417,928 accession × CIK
  records
- Missing acceptance timestamps among Item 2.02 records: 0
- Exact accession-CIK content conflicts: 0

The acquisition preserves joint filers as separate accession × CIK records for PIT
issuer mapping while retaining unique accession counts for reconciliation.

## Terminal result

**Verdict: `kill_line`**

**Status: `i0_complete`**

The sole failed integrity gate was the frozen global PIT mapping floor:

- Mapped original filer records: 347,917 / 413,636
- Mapping rate: **84.1119%**
- Frozen minimum: **95%**
- No covering CIK/listing window: 47,063
- Ambiguous covering listings: 17,241
- Non-US-primary-common after deterministic mapping: 1,415

Even resolving every ambiguous record favorably would produce only **88.2800%** mapping,
still below the frozen 95% floor. The threshold was not changed after tape inspection.

All other integrity gates passed. Both power gates passed, but power cannot override an
integrity failure.

| Gate | Result | Evidence |
|---|---:|---|
| I1 reconciliation | PASS | All quarterly expected/fetched/parsed form counts agree |
| I2 accession provenance | PASS | 0 duplicate conflicts |
| I3 Item 2.02 semantics | PASS | 409,296 accessions; 417,928 filer records; 0 conflicts |
| I4 acceptance timestamps | PASS | 417,928 / 417,928 valid (100%) |
| I5 PIT mapping | **FAIL** | 347,917 / 413,636 mapped (84.1119%) |
| I6 mapping composition | PASS | Worst material-year unmapped rate remained below the frozen composition ceiling |
| I7 session calendar | PASS | 0 mapped filings lacked a strictly later regular-session open |
| I8 power basis | PASS | Frozen pre-existing count-only basis present and hashed |
| P1 usable years | PASS | 20 usable years versus floor 10 |
| P2 count upper bound | PASS | 346,150 canonical anchors versus 16,125 required |

Additional source-only counts:

- Conservative canonical anchors: 346,150
- Unique mapped issuers: 9,614
- Unresolved Item 2.02 amendments excluded: 4,292
- Maximum issuer share: 0.07425%
- Maximum known-session share: 0.12480%

## Power basis

The optimistic count-only screen used the frozen CFOB Gate-1a basis, not any SEC-8K
reaction or outcome variance:

- Effective dispersion: 0.38
- Primary clustered threshold: 2.5
- 80% power beta quantile: 0.841621
- Target future effect: +1.00%
- Required events: 16,125
- Observed count upper bound: 346,150
- Source artifact SHA-256: `0e1122359139e5eb0628fe5ce339208bcb36c66a56e3f70028a6102733e9fa16`

## Replay and hashes

The sealed evaluator replayed byte-identically from the recorded manifest.

- Manifest path: `fixtures/real-continuous/reports/sec8k-i0/sec8k-i0-manifest.json`
- Manifest file SHA-256: `66ec5b7365e84ef4e18b667aba0c661109a916859d0f98d6ae7bd511d712a830`
- Artifact path: `fixtures/real-continuous/reports/sec8k-i0/sec8k-i0-artifact.json`
- Artifact file SHA-256: `62b75b7712d8a608894b0abf07a85f72a511209d64b4cbce280721b428a81a6f`
- Artifact self-hash: `355ead2c7215e39efe2adde5c57330ccbffe1a7fc06157c6276a157554431c15`
- Byte-identical replay: PASS

Manifest section hashes:

- Filings: `80a9da2106801f0b9b09e6b97c4c20738a5236783b47f51a3ec0df20b4503c6c`
- Listings: `fafb4b391b770d85cad50a8693f5d554a583ea05e1ad60f0694c8c466e58ca92`
- Sessions: `a6782c8046f252b96defb3c1a604e343f001d0b436511e4ffad6af2424388e9c`
- Reconciliation: `2b383f44e19bae0e8979fecd578d17b874b67f912756c47798b0ffbb97a11100`
- Power basis: `2c2fb246935abe529b38df8eb147c22dde84d1a95e20cb82ccdc9be0f0f09805`
- Provenance: `d317d68604daf1c0d5f572ecc099682f10af27f3c7bbb0ffa9373ba61046d964`

## Stop disposition

The source audit succeeded operationally and failed its frozen mapping-integrity gate.
This is a terminal `kill_line`, not evidence that the named drift hypothesis is false
or true. Full-Stop resumes. No F0 PRD is authorized from this result, and E1 remains
blocked.
