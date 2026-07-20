# Step 3 Results — Spec-Compliant Baseline + §2.5 Control

**Date**: 2026-07-19
**Code**: main @ `74d6ac7` (PR #57 merged) + uncommitted WIP streaming loader
  (`src/invest/adapters/fixtures_json.py`, `cli.py`; 67 adapter tests pass).
**Fixture**: `fixtures/real-continuous/` — 1.3 GB `bars.json`, 8,869,021 bars,
  6,477 symbols, 2017-12-29 → 2025-12-31 (2019-01-02 → 2025-12-31 generation span).
**Split**: IS/OOS at 2023-01-03. Costs: slippage 5bps/side, tax 15% per winning
  trade. Exit: ten-day-low.

## Commands

```
# §2.5 spike-detector control (naïve MomentumScanner, identical replay)
invest-backtest \
  --universe fixtures/real-continuous/bars/universe.json \
  --bars    fixtures/real-continuous/bars/bars.json \
  --market-context fixtures/real-continuous/market-context.json \
  --strategy benchmark --split-date 2023-01-03

# core spec-compliant
invest-backtest ... --strategy core --split-date 2023-01-03

# uncapped spec-compliant (risk capital 1,000/trade, capital gates off)
python fixtures/real-continuous/reports/uncap_backtest.py
```

Reports saved to `fixtures/real-continuous/reports/`:

- `backtest-benchmark-control.json`
- `backtest-core-speccompliant.json`
- `backtest-uncapped-speccompliant.json`

## Results

| Run | Scanner | Trades | Net P&L | Hit | Exp/trade | IS exp | OOS exp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline (interim, pre-PR#57) | core | 125 | −7,743 | 20.0% | −61.9 | −86.1 | −15.8 |
| **benchmark-control** (§2.5) | naïve | 396 | −7,099 | 38.1% | −17.9 | −48.7 | **+30.0** |
| core-speccompliant | core | 502 | −29,198 | 28.9% | −58.2 | −85.7 | −17.9 |
| uncapped (interim) | core | 4,683 | −840,828 | 20.9% | −179.5 | −281.6 | −68.3 |
| uncapped-speccompliant | core | 3,451 | −313,323 | 32.8% | −90.8 | −129.0 | −49.9 |

> **Comparability caveat**: core-speccompliant net dollar P&L is NOT comparable
> to the interim baseline — PR #57 dropped risk from 1% to 0.35% (~2.85× less
> capital per trade). Compare per-trade expectancy and trade count, not net P&L.
> The uncapped runs are comparable to each other (risk capital 1,000/trade).

## Findings

1. **Spec-compliant changes improved the signal-edge measurement.** Against the
   uncapped view (raw cross-sectional edge, capital gates off), the
   spec-compliant config is materially better than the interim config:
   - hit rate 20.9% → **32.8%**
   - per-trade expectancy −179.5 → **−90.8**
   - OOS expectancy −68.3 → **−49.9**
   - trade count 4,683 → 3,451 (fewer but higher-quality entries via ranked fill)

   The structural stop `min(breakout-day low, entry − 2×ATR(20))`, the
   `entry + 2×ATR(20)` take-profit, the 10-session cooldown, and ranked
   (momentum → 52w-high proximity → liquidity) fill all helped. Still negative,
   but bleeding far less per trade.

2. **The §2.5 control beats the core strategy out-of-sample.** This is the
   critical finding. The naïve spike-detector scanner (`MomentumScanner`,
   `--strategy benchmark`) under identical replay assumptions:
   - **OOS expectancy +30.0**, hit 38.1%, net OOS **+4,646** — *positive*.
   - The core momentum-selection scanner: OOS expectancy **−17.9**, hit 28.9%.

   The core does **not** beat its control out-of-sample. This **fails the
   plan's §2.5 acceptance gate** ("the after-cost strategy must beat the §2.5
   control"). A naïve scanner that simply buys spikes is a higher-bar edge than
   the momentum-selection ranking adds in this universe/config.

3. **The edge problem is the signal/ranking, not the exits.** Consistent with
   the Step 2 event study (drift positive at 20–120 sessions, zero/negative at
   short horizons, path hits −1R before +1R on a coin flip): the spec-compliant
   structural stop helped materially, but the momentum *selection* adds nothing
   over a naïve scanner OOS. The exits were the first-lever the event study
   pointed at; fixing them confirmed they were Part Of The Problem, but the
   ranking is the remaining missing-value locus.

## Incident: 2026-07-19 ~12:19 RAM collapse

The first attempt launched all three runs **in parallel** against `bars.json`.
The old `JsonFixtureReader` (`fixtures_json.py`) reads the whole file into a
Python string, then `json.loads` materializes a ~9 GB dict phase, then
`model_validate` builds pydantic `DailyBar` models on top — **~10–12 GB peak
per process**. Three concurrent ≈ 30 GB on a 16 GB machine → collapse; all
three report files truncated to 0 bytes at 12:19.

Smoke-test measurement on the real fixture (per-bar byte costs):

| Stage | RSS for 100 MB JSON text | extrapolated 1.3 GB |
| --- | ---: | ---: |
| raw file string | ~100 MB | ~1.3 GB |
| `json.loads` → dicts | ~676 MB | ~8.8 GB |
| `model_validate` → DailyBar | +~100 MB | +~1.3 GB |

**Fix applied** (WIP, uncommitted): a streaming loader replaced the full-file
`json.loads` with incremental JSON decode (no giant dict phase retained) and a
compact forward-only bitmap per symbol for exact-duplicate detection.
`JsonFixtureReader.load()` also accepts `start`/`end` for fixture-source date
filtering; `cli.py` wires `--start`/`--end` into the fixture source.

Streaming-loader smoke test on the real fixture:

- 8,869,021 bars / 6,477 symbols loaded in **59.3 s**
- peak RSS **4.87 GB** (vs ~10–12 GB old)

The three runs were then executed **sequentially** (one process at a time),
wall time ≈ 2.6 h + 2.5 h + 1.7 h, all completed (runner exit 0), all three
reports valid JSON.

> **Operational rule for this machine**: never run two fixture loads
> concurrently. 16 GB RAM; one load peaks ~5 GB with the streaming loader,
> ~10–12 GB with the old loader.

## Provenance caveat

These reports were produced by **uncommitted WIP code** (`74d6ac7+dirty`).
The streaming loader has a semantic change (per-bar streaming + fixture-source
`--start`/`--end` filtering) and `trading-system/spec.md:856-860` references a
byte-identical-benchmark spec scenario. Before treating these numbers as
durable measurement, the streaming loader should be committed (full test suite
- spec review) and the reports either re-validated or re-run against the
committed revision. The 67 adapter-level tests pass, but that is not a full
suite.

## Next steps (proposed)

1. **Commit the streaming loader** with full test suite + spec review (direct
   commit or a small SDD change). It's blocking provenance of every report
   after this one.
2. **Diagnose why the ranking underperforms the naïve scanner** before Step 4's
   regime gate. The §2.5 gate failure + control-positive-OOS is stronger
   evidence than the regime-gate hypothesis: if the selection adds nothing over
   a spike-buying control, gating by market regime does not rescue it — it
   re-asks "what does the momentum ranking encode that a naive scanner doesn't,
   and does it have cross-sectional alpha?" Candidate investigations: per-decile
   of momentum rank vs forward returns (does rank order predict drift), and the
   §2.5 control's trade-level attribution (is its OOS profit a few forced-close
   names or broad).
3. **Step 4 (regime gate) is conditional** on the signal having drift. The
   control comparison argues for re-examining the signal before adding a gate
   on top of it.
