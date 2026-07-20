# Phase 2b results — concentration autopsy

**Date:** 2026-07-20  
**Driver:** `fixtures/real-continuous/reports/research_phase2_autopsy.py`  
**Artifact:** `fixtures/real-continuous/reports/phase2-concentration-autopsy.json`  
**Plan:** `docs/research/phase2-concentration-autopsy-plan.md`  
**Parent:** Phase 2 NO-GO · #62 · issue #64

## Verdict

### residual_hope: **DIE**

Promotion remains **blocked** (Phase 2 year concentration). This field is die|survive only — never GO.

### K2 legs

| Leg | Result | Detail |
| --- | --- | --- |
| Leave-2020 mean > 0 | PASS | 9.436660111300162151408642665 |
| Leave mean > ½ full-book mean | FAIL | leave 9.436660111300162151408642665 vs half of 56.1160824265044444156249482 = 28.0580412132522222078124741 |
| Majority remaining folds mean > 0 | PASS | 5/6 |
| S2 mean trade−SPY excess > 0 | FAIL | -101.9837094141070704441280401 |

Reasons:

- leave-2020 mean 9.436660111300162151408642665 ≤ half full-book mean 28.0580412132522222078124741
- S2 mean trade−SPY excess ≤ 0 (-101.9837094141070704441280401)

## Leave-year book (pre-tax, 5 bps/side)

Published full-book mean (denominator): **56.1160824265044444156249482**

| Book | n | Mean exp | Median exp | Hit | Net P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| Leave-2020 | 170 | 9.436660111300162151408642665 | 8.0715773993725239419095395 | 0.5058823529411764705882352941 | 1604.232218921027565739469253 |
| Non-FC | 83 | 97.07168980877541359506445263 | 63.006975 | 0.5542168674698795180722891566 | 8056.950254128359328390349568 |
| FC only | 87 | -74.16917281847507773161931397 | -22.253626882515759610536194 | 0.4597701149425287356321839080 | -6452.718035207331762650880315 |

## Remaining walk-forward folds

| Year | n | Mean exp | Median exp | Net P&L |
| ---: | ---: | ---: | ---: | ---: |
| 2019 | 34 | 137.5253716223790230121291882 | 104.569354911821924165536832 | 4675.862635160886782412392398 |
| 2021 | 25 | 62.66673876991201730608252176 | 34.547689438527458400184325 | 1566.668469247800432652063044 |
| 2022 | 33 | -290.7535215535265194060916892 | -103.931627837893989801322561 | -9594.866211266375140401025745 |
| 2023 | 22 | 62.73701897037128731177948809 | -14.907845980744722661839425 | 1380.214417348168320859148738 |
| 2024 | 28 | 110.7230415059132156484872358 | 273.4607824134398595374757175 | 3100.245162165570038157642602 |
| 2025 | 28 | 17.00384808089204043068743629 | 9.209789676875832000295011 | 476.107746264977132059248216 |

## S2 trade-window SPY

- Proxy: SPY
- Window: entry_fill_open_to_exit_fill_open
- Notional: qty * entry_price (raw)
- Mean excess (trade after-cost − matched SPY): **-101.9837094141070704441280401**
- n trades: 170

## Pause-default

Next research budget defaults to **pause** on the price-event portfolio residual line. Form-4 PIT audit or a new concentration-policy PRD requires an explicit re-open. No ranking / Quiet Drift / DAMB package auto-start.

## How to re-run

```bash
uv run python fixtures/real-continuous/reports/research_phase2_autopsy.py
```

Requires committed `phase2-structure.json`. SPY opens load from `spy-opens-sidecar.json` when present and complete; otherwise refresh via Yahoo chart API for SPY daily opens. Unit CI must not load multi-GB bars.
