# Research Plan After the First Backtest Failure

**Status:** Active research agenda  
**Created:** 2026-07-18  
**Evidence window:** 2019-01-02 to 2025-12-31  
**OOS split used:** 2023-01-03  

## Purpose

Record what the first continuous Core backtest taught us and define the ordered,
falsifiable research program for changing the strategy. This document is the
cross-session starting point for future strategy research; it should be updated
when an investigation resolves one of the questions below.

## Evidence That Triggered This Plan

Source artifacts:

- `fixtures/real-continuous/reports/backtest-baseline.json`
- `fixtures/real-continuous/reports/backtest-uncapped.json`
- `fixtures/real-continuous/reports/uncap_backtest.py`
- `fixtures/real-continuous/reports/README.md`

### Baseline portfolio

The $100,000 capped portfolio produced 125 trades. It ended at $92,257 after the
configured 5 bps per side and per-winning-trade 15% tax haircut. The same fixed
trade ledger was +$9,597 at raw prices and +$7,391 after slippage alone, but the
sample was dominated by the capital gate and arbitrary alphabetical selection
among simultaneous candidates. Its raw trade-level t-statistic was only 0.34,
and its best trade exceeded total raw profit.

### Uncapped signal experiment

The constant-risk uncapped experiment removed capital contention and tested
4,683 context-safe trades at approximately $1,000 risk per trade:

| Accounting | P&L | Expectancy | Profit factor | Naive trade t-stat |
| --- | ---: | ---: | ---: | ---: |
| Raw prices | -$106,030 | -$22.64 (-0.023R) | 0.972 | -0.52 |
| 5 bps per side | -$297,534 | -$63.53 (-0.064R) | 0.924 | -1.46 |
| Configured tax model | -$840,828 | -$179.55 (-0.180R) | 0.785 | -4.74 |

The full-period binary signal therefore has no demonstrated average edge. The
OOS segment improved before tax—raw +$248,299, profit factor 1.135, t=1.53—but
the effect was not statistically persuasive, fell to t=0.96 after slippage, and
was regime-dependent: 2023 and 2024 were positive while 2025 was negative.

### Exit diagnosis

| Exit | Trades | Raw P&L |
| --- | ---: | ---: |
| 1x ATR hard stop | 3,413 | -$3.585M |
| Trailing channel | 711 | +$2.361M |
| Context forced close | 528 | +$1.026M |
| Open at end | 31 | +$91.7k |

Of the 3,413 stopped trades, 960 stopped on the entry day, 1,833 stopped within
three calendar days, and the median stop duration was three calendar days. This
creates the central unresolved question: **is the accepted entry signal bad, or
does immediate next-open entry plus the 1x ATR stop destroy a valid signal?**

## Research Principles

1. Diagnose signal edge independently of exits before tuning parameters.
2. Change one conceptual component at a time.
3. Use small, predeclared grids and record every trial, not only winners.
4. Keep risk per trade constant when comparing stop widths.
5. Treat pre-tax, after-execution-cost performance as the primary alpha metric;
   report taxes separately.
6. Cluster inference by entry date because same-day signals are correlated.
7. Select broad, stable parameter regions rather than historical maxima.
8. The examined 2023-2025 period is no longer an untouched holdout. Use rolling
   walk-forward evaluation for research, then freeze the strategy before a new
   future holdout.

## Ordered Research Program

### 1. Signal event study — highest priority

**Hypothesis:** The current accepted signal may have positive forward drift that
is obscured by entry and exit mechanics.

For every accepted signal, independent of portfolio gates and exits, calculate:

- Next-open to 1, 5, 10, 20, 60, and 120-session returns
- Maximum favorable and adverse excursion
- Probability of reaching +1R before -1R
- Results by entry year and ex-ante market regime
- Raw and realistic after-cost results
- Corporate-action and eligibility outcomes as separate cohorts
- Date-clustered confidence intervals

**Decision:**

- Positive forward drift but negative trades -> research confirmation/stops.
- No forward drift -> redesign the signal and ranking.
- Edge limited to high-score cohorts -> replace binary acceptance with ranking.

### 2. Audit context-forced exits

**Hypothesis:** Context exits are valid but materially subsidize reported
performance and may mask the behavior of the normal exit policy.

Partition the 528 forced closures into corporate actions, acquisitions,
delistings, eligibility/liquidity changes, and invalid/missing context. Compare
same-day-low, same-day-open, and prior-close valuation as sensitivity cases,
while verifying that each unsafe status was knowable at the simulated time.

**Rejection condition:** If apparent signal edge depends on invalid timing or a
single event category, do not attribute that edge to the scanner.

### 3. Replace binary acceptance with continuous ranking

Persist component scores for:

- 12-1 momentum percentile
- Distance from the 52-week high
- Breakout magnitude normalized by ATR
- Short/long trend strength and slope
- Relative-volume surprise
- Liquidity and spread proxies

Test each feature by decile before combining them. Only create a simple composite
if higher score cohorts show a monotonic improvement in after-cost forward
returns. Portfolio selection must take the top-ranked candidates before applying
capital gates; alphabetical ticker order must not allocate scarce capital.

Initial portfolio comparisons: top 3/5/10 candidates and top 5%/10%/20% of
signals, all at constant risk.

### 4. Test entry confirmation and initial stops

Run a small, predeclared comparison:

**Entries**

- Immediate next open (control)
- The intended confirmed-entry behavior from SPEC section 2.4
- One additional close holding above the breakout level
- Optional pullback/retest entry

**Initial stops**

- 1x ATR (control)
- 1.5x ATR
- 2x ATR
- 3x ATR

Recalculate quantity so each variant risks the same dollars. Diagnose how many
same-day and first-week stops each variant removes and whether wider stops create
positive after-cost R expectancy rather than merely delaying losses.

### 5. Test trailing exits after the initial-stop region is known

Hold the selected entry and initial-stop family fixed, then compare 10, 20, and
40-session trailing channels. Do not optimize entry, initial stop, and trailing
window simultaneously.

### 6. Test ex-ante regime filters

Only after signal/exit diagnosis, compare a small set of economic filters:

- Broad-market price above its 200-day moving average
- Percentage of eligible stocks above their 200-day average
- Realized broad-market volatility
- Cross-sectional return dispersion

The objective is improved consistency and tail behavior across rolling folds,
not reproducing the favorable 2023-2024 period.

### 7. Portfolio and execution research

Only optimize portfolio rules after positive signal-level expectancy is shown:

- Maximum exposure of 25%, 50%, and 75%
- Maximum 5, 10, and 20 positions
- Sector and correlated-position limits
- Volatility-scaled risk
- Score-based replacement/hysteresis rules
- Liquidity-dependent spread and market-impact costs
- Interest on idle cash
- SPY, IWM, and momentum-factor benchmarks

## Proposed Acceptance Gates

A candidate should not advance merely because it has the best historical P&L.
Require:

- Positive after-cost expectancy across most walk-forward folds
- Profit factor around or above 1.10 across a broad parameter region
- No single trade or year contributing more than roughly 25% of total profit
- Positive date-clustered confidence evidence
- Drawdown and underwater duration acceptable relative to its benchmark
- Deflated Sharpe or another multiple-testing correction that accounts for all
  tried variants
- Positive economics before favorable tax assumptions

## Current Research Decision

The next implementation should support the **signal event study and context-exit
audit**, not a broad stop-loss optimizer. Those results determine whether the
next strategy change belongs in the signal/ranking layer or the entry/exit layer.

## Research References

- Daniel, K. and Moskowitz, T., [Momentum Crashes](https://www.nber.org/papers/w20439)
- Kaminski, K. and Lo, A., [When Do Stop-Loss Rules Stop Losses?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338)
- Novy-Marx, R. and Velikov, M., [A Taxonomy of Anomalies and Their Trading Costs](https://academic.oup.com/rfs/article-abstract/29/1/104/1844518?login=false)
- Bailey, D. and López de Prado, M., [The Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)
