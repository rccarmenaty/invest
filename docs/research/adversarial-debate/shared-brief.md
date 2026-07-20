# Adversarial Strategy Debate — Shared Brief

**Date:** 2026-07-20  
**Repo:** invest (main @ post-PR#57)  
**Task:** Propose a falsifiable path to a trading edge (improve / pivot / invent), grounded in completed experiments + external research (arXiv, papers, industry).  
**Role:** You are one of three adversarial judges. Argue hard for YOUR proposal. Attack weak reasoning. Prefer real edge over clever backtests.

## System (what exists)

- Point-in-time market context from Sharadar (SEP + ACTIONS + TICKERS)
- Momentum-selection Core scanner vs naïve spike-detector benchmark (§2.5 control)
- Spec-compliant baseline: ranked same-day fill (momentum → 52w-high proximity → liquidity), structural stop min(breakout-day low, entry−2×ATR(20)), TP entry+2×ATR(20), 10-session cooldown, RISK_PER_TRADE 0.35%
- Trailing channel / time-stop / ATR-trail exits available
- Uncapped constant-risk experiment harness; event study; forced-close audit
- Memory-bounded streaming fixtures; fail-closed if open position's last bar predates replay end

## Evidence window

- Continuous fixture: ~2019-01-02 → 2025-12-31, ~6.5k symbols, ~8.87M bars
- IS/OOS split used: 2023-01-03
- Costs: 5 bps/side + 15% tax on winners (primary alpha metric = pre-tax after costs)

## Experiment results (must internalize)

### 0 — First continuous Core failure
- Capped $100k: 125 trades, net −7.7k; capital-gate dominated (most skips max-equity-deployed)
- Uncapped (~$1k risk/trade): 4,683 trades; raw PF 0.97, t=−0.52; after costs −841k
- Exit mix (uncapped interim): 1×ATR stop 3,413 trades (−$3.59M); trailing channel 711 (+$2.36M); context FC 528 (+$1.03M)

### 1 — Forced-close audit
- 528 FCs: mostly corporate-action policy (kind-blind blockers act as accidental TPs near highs)
- FC profit is a **policy artifact**, not alpha. Do not harvest FC.

### 2 — Signal event study (n≈12,295 position-blind accepted signals)
| Horizon | Mean | clustered t | Hit>0 |
|---|---:|---:|---:|
| +1d | −0.08% | −1.01 | 48.8% |
| +5d | −0.04% | −0.31 | 50.9% |
| +10d | +0.43% | +2.44 | 52.3% |
| +20d | +0.98% | +3.31 | 53.6% |
| +60d | +3.49% | +7.49 | 52.0% |
| +120d | +7.11% | +13.6 | 56.5% (survivorship caveat) |

- Years: 2021–2022 negative at h20; 2023–2024 strong; 2025 weaker
- Excess vs same-date eligible-universe mean (h20): +0.36%, t=1.78 (thin CS alpha; much is beta)
- Race to ±1×ATR within 60d: down-first 6208 vs up-first 5848 → P(+1R first)≈48.5%
- **Decision rule fired:** long-horizon drift exists; short path kills tight stops

### 3 — Spec-compliant baseline + §2.5 control
| Run | Trades | Net P&L | Hit | Exp/trade | OOS exp |
|---|---:|---:|---:|---:|---:|
| interim capped core | 125 | −7.7k | 20% | −62 | −16 |
| **benchmark §2.5 control** | 396 | −7.1k | 38% | −18 | **+30** |
| core-speccompliant | 502 | −29.2k | 29% | −58 | −18 |
| interim uncapped | 4683 | −841k | 21% | −180 | −68 |
| uncapped-speccompliant | 3451 | −313k | 33% | −91 | −50 |

- Spec changes improved uncapped bleed (hit↑, exp less negative) but **still no edge**
- **Core fails to beat naïve spike control OOS** — ranking adds no clear value
- Dollar P&L not comparable across risk 1%→0.35%; use per-trade expectancy

### 4 — Corrected 2022–2025 matrix (NOT published)
All three variants completed 1003 scan days then **fail-closed** on stale terminal opens:
- Benchmark: VG2 last bar 2022-07-20
- Capped Core: ISEE last bar 2023-07-10
- Uncapped Core: CONE last bar 2022-03-24  
(replay end 2025-12-31). Safeguard correct; no valid multi-year P&L from that matrix.

## Research principles already agreed
1. Diagnose signal independent of exits before tuning
2. One conceptual component at a time
3. Constant risk when comparing stops
4. Pre-tax after costs primary; tax secondary
5. Date-clustered inference (same-day signals correlated)
6. Prefer broad stable regions; deflated Sharpe / multiple-testing discipline
7. 2023–2025 no longer untouched holdout — use walk-forward; freeze before new future holdout

## Hard constraints for proposals
- Must be implementable on this stack (daily US equities, PIT context, existing scanners/exits)
- Must include **falsifiable acceptance gates** and **rejection conditions**
- Must cite external research (arXiv / NBER / journal) for the economic mechanism
- Must explain why it survives: transaction costs, short-horizon path risk, FC contamination, ranking failure, regime dependence, multiple testing
- Forbidden: inventing numbers as if already measured; claiming edge without a measurement plan
- Prefer ideas that exploit the **long-horizon drift + thin CS alpha** finding rather than denying it

## Required output structure (strict)

# Proposal title
## Thesis (1 paragraph)
## Mechanism (why edge should exist economically)
## Literature anchors (3–8 citations with arXiv/DOI/URL + one-line relevance)
## Concrete strategy design (entries, ranking, exits, portfolio, costs assumptions)
## How it differs from current Core / §2.5 control
## Why prior experiments predict this might work (map to Steps 0–3)
## Why it might fail (steelman opposition)
## Measurement plan (ordered experiments, sample design, stats)
## Acceptance / rejection gates
## Implementation cost on this repo (files / new modules / data needs)
## Confidence (0–100) and single sharpest risk

Then:
## Attacks on the other two archetypes
Attack these alternative directions (even if you also like parts of them):
A) **Hold longer / widen path** — keep breakout signal, fix horizon & stops only  
B) **Ranking overhaul** — continuous scores, deciles, composite; kill binary accept  
C) **Regime / risk-on gate** — 200DMA / breadth / vol filter before any signal  

Argue which archetype is most dangerous (overfit / no edge / implementation trap).

## Final one-liner
What would you bet your own capital research budget on next, and what single experiment proves it?

