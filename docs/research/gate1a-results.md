# Gate 1a results — h60 excess vs universe

**Date:** 2026-07-20  
**Driver:** `fixtures/real-continuous/reports/research_gate1a.py`  
**Artifact:** `fixtures/real-continuous/reports/gate1a-excess.json`  
**Helpers:** `src/invest/application/event_study_excess.py`

## Verdict

**Gate 1a: PASS**

Predeclared rule: h60 same-date eligible-universe excess mean > 0 and
date-clustered t ≥ 2.5.

| Horizon | n | Mean excess | Clustered t | Hit >0 | Median excess |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 20 (regression) | 11,977 | +0.36% | 1.78 | 49.1% | −0.19% |
| **60 (primary)** | **11,489** | **+1.89%** | **5.30** | 49.0% | −0.42% |
| 120 (flagged) | 10,681 | +2.26% | 4.98 | 49.0% | −0.64% |

h20 matches Step 2 `event-study.json` exactly (mean +0.3647%, t 1.783) — same
cohort methodology.

## Interpretation

1. **Long-horizon residual is not pure beta at h60.** Mean excess clears the
   kill gate with room (t=5.3). Quiet Drift / fixed-horizon work is *not*
   dead on Gate 1a alone.
2. **Median excess is still negative** at all three horizons. The mean is
   right-tail driven; portfolio expectancy may differ from mean event-study
   excess.
3. **Regime still matters:** 2021 h60 excess −6.74% (t −5.85); 2024 +5.16%
   (t 6.98). Walk-forward must include crash years.
4. **FC cohort is not the whole story:** non-FC symbols still +1.61% (t 3.14)
   at h60; FC symbols +2.24% (t 5.91).
5. **ID ranking is weak (Gate 1b not claimed):** q1 (smoothest) +2.16% vs q5
   +1.61% (spread +0.55pp, direction smooth_better). Not a strong monotone
   ladder (q4 > q3). Prefer **unranked fixed-horizon** next unless a formal
   spread t-test clears a predeclared Gate 1b.

## Next (meta-judge Phase 2)

Gate 1a passed → run clean structure test:

- §2.5 naïve event, **no price stop, no TP, exit open T+60**
- random-admission control under slot cap
- ranking only if a frozen single feature later clears Gate 1b
