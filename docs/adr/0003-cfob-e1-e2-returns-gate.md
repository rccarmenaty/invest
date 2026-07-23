# CFOB E1/E2 returns gates — two-stage placebo/block-bootstrap acceptance

Stages D and F0 counted and integrity-checked insider purchase clusters but measured **no returns** (`capital_go` false by construction). E1/E2 is the returns stage of the CFOB line, grilled 2026-07-23 (this ADR records that session). It is a **two-gate conjunctive funnel** on a **single common frozen cohort**, decided in full before any return was inspected. This ADR freezes every constant and the rationale for the choices that diverge from an off-the-shelf event study.

Companion glossary terms in `CONTEXT.md`: **E1 residual-drift gate**, **E1 primary gate (block bootstrap)**, **E2 benchmark-residualized gate**, **Common frozen cohort**, **Placebo embargo**. Inherits the frozen Stage-D qualification protocol (code-P, ≥$10k gross, 10-day staleness cap, 30-day cluster window, ≥2 distinct insiders, ≥$2M 20-bar median dollar-volume habitat, 252-bar history) and ADR 0002's gate-law divergences.

## Roles and verdict wiring (Q1, Q5)

- **E1** advances the research line; a green E1 is **provisional timing evidence, not alpha**. **E2 is required for final acceptance.**
- The gates are **conjunctive at the primary 25 bps specification**: the line is accepted only when the *same* common frozen cohort clears **both** E1 `p ≤ 0.005` **and** E2 `p ≤ 0.005`.
- Gates operate at **cohort level only** — no per-cluster filtering, reranking, or survivor selection between gates.
- A red gate = **Promotion block** naming the failing gate, or a **Program kill**. `capital_go` remains a separate human decision even on a green E2 (portfolio implementation, hedge-leg costs, capacity are out of scope here).

## Considered options

### 1. Return, cost, and the E1 statistic (Q2–Q4)

- **Chosen return:** open-to-open 60-session simple return on the frozen adjusted-price convention; dates without a complete forward horizon are **inadmissible** (excluded, not truncated). Rejected truncated/partial horizons — they smuggle a look-ahead/survivorship bias.
- **Chosen cost:** **25 bps round-trip** primary, subtracted once from the gross return; 10 and 50 bps are **non-gating diagnostics**. Keeps the "stricter than the 10 bps used elsewhere" comparison apples-to-apples (ADR 0002); per-side costing rejected (would collide with the ladder's own 50 member).
- **Chosen E1 statistic:** per cluster `dᵢ^E1 = R_obs^net − mean(R_placebo^net)`, the within-ticker date-shuffle placebo as control. Same-window universe excess is **diagnostic only** (ADR 0002 already demoted raw-excess-vs-universe from primary); same-window *market* movement is deferred to E2, not folded into E1. Rejected adding a universe/market leg to E1 — double-counts against the placebo.

### 2. E1 inference gate — null-imposed circular stationary block bootstrap (Q6–Q8, Q15)

Parametric clustered-t was **rejected as the gate** (kept as a diagnostic). The dominant correlated-error structure is calendar overlap — hundreds of different tickers entering the same market window (2008, 2020) whose 60-session returns co-move for market, not insider, reasons — and a naïve or even month-clustered t under-states it.

- **Chosen:** canonical **circular Politis–Romano stationary bootstrap** over the complete ordered sequence of known-time calendar-month buckets, **including empty months**. Each replication starts at a uniformly chosen month; at each next position it restarts at another uniform month with probability **q = 1/6** or advances one circular month otherwise → **geometric block lengths, expected 6 months**. Exactly the original number of month positions is emitted (terminal block truncated).
- A selected month **carries all of its recentered cluster values**; repeated months repeat their clusters, empty months contribute none, so the bootstrap cluster count varies by replication (intended — preserves real event-time clumping). Months are **not** equal-weighted and the cluster count is **not** forced to its observed value.
- **Null imposition:** `dᵢ⁰ = dᵢ − θ̂` where `θ̂ = T(d)`; translation-equivariance of `T` gives `T(d⁰) = 0` in expectation. Placebo dates are **not** redrawn inside replications.
- **A path with zero clusters is discarded and regenerated; the discard count is recorded.**
- **Gate:** one-sided `p = (1 + K)/(B + 1)`, K = replications whose statistic is **≥** the observed statistic, **B = 99,999 valid** replications, **α = 0.005**.
- **Block length = 6 months** matches the ~3-trading-month overlap horizon with margin. Predeclared-fixed beats data-snooped; expected lengths 1/3/12 months, the corrected Politis–White selector, non-circular blocks, and iid/month-clustered/ticker t-statistics are **all non-gating diagnostics**.
- **B = 99,999** (not 10,000): a 0.005 hard boundary needs fine-grained p resolution; MC error on p≈0.005 at B=1e5 is negligible.

### 3. The cohort estimator T(d) (Q12)

- **Chosen:** equal-weight arithmetic mean after **two-sided 1% winsorization** (clip, do not drop). For every sample handed to `T` — the observed cohort and every bootstrap replication — the empirical P1/P99 are recomputed from that sample's own values:
  ```python
  q_low, q_high = np.quantile(values, [0.01, 0.99], method="linear")
  winsorized = np.clip(values, q_low, q_high)   # inclusive clip, no drops
  theta = winsorized.mean()                      # equal weight, one vote per cluster
  ```
  float64 arithmetic; no NaNs in the input to `T`; no rounding before the percentile calculation; `method="linear"` named explicitly (not "the NumPy default") so a library-version change cannot silently alter the frozen estimator.
- **Rejected:** trimming (dropping tails — changes effective n per replication); reusing observed-cohort cutoffs inside replications (breaks `T` as a single functional); capitalization/liquidity/volatility/beta-precision/placebo-precision weighting (equal-weight matches the density-count philosophy — a cluster is the unit; the estimand is the average effect across qualifying clusters).
- **Small cohorts:** if the fully support-qualified common cohort has **fewer than 2,000 clusters**, both E-stages return **`underpowered_stop`** and no statistic or p-value is attempted. This is an **operational admissibility floor, not a power guarantee** — true precision also depends on calendar spread, crisis concentration, `dᵢ` dispersion, and the block structure, all of which are reported as diagnostics.

### 4. E2 benchmark and residual arithmetic (Q9, Q10, Q13)

E2 is a **habitat-factor-adjusted timing test** — explicitly **not** unrestricted asset-pricing alpha and **not** an investable portfolio return. The characteristic-matched control of ADR 0002 was **rejected on entitlement** (no daily cross-sectional characteristic panel; market-cap history not entitled — METRICS snapshot-only, DAILY samples). Fixed beta-1 was **rejected** in favour of an estimated beta.

- **Factor:** daily **leave-one-out equal-weight** return of the point-in-time eligible CFOB habitat (focal ticker excluded — no self-inclusion), on aligned daily open-to-open returns.
- **Beta:** date-specific single-factor **OLS with intercept** over the **252 preceding market sessions**, `≥ 200` valid focal↔factor pairs, no imputation, no backward extension. The window ends at the last completed market close preceding the exact public known-time timestamp; when only the filing date is known, it ends on the previous session.
- **Benchmark (the refinement that matters):** beta is applied to **each daily habitat return before compounding** —
  `Bᵢₜ^β = ∏_{s=1..60} (1 + β̂ᵢₜ · h₋ᵢ,ₜ,ₛ) − 1` — **not** the approximation `β̂·[∏(1+hₛ)−1]`.
- **Residual:** `eᵢₜ = Rᵢₜ^net − Bᵢₜ^β`, with **no estimated intercept** in the primary benchmark. Rationale: `α̂` is the ticker's idiosyncratic drift, and the within-ticker observed-minus-placebo construction already removes the ticker's average residual drift across admissible dates — subtracting `α̂` too is the crude double subtraction the design forbids. So **beta removes contemporaneous common habitat movement; the placebo removes unconditional drift/alpha.**
- **Collapse:** `dᵢ^E2 = e_obs − (1/M)·Σⱼ e_placebo,ⱼ`, then the **same** null-imposed circular block-bootstrap gate as E1.
- **Habitat factor is gross** (a risk-adjustment benchmark, not an assumed traded hedge); costs apply only to the focal traded leg.
- **Diagnostics (non-gating):** intercept-inclusive benchmark `∏(1+α̂+β̂h)−1`, log-return residualization, unit-beta habitat subtraction, SPY-based specs, Vasicek/Blume shrinkage, alternative estimation windows.

### 5. Common frozen cohort, breadth, and placebo admissibility (Q10, Q11, Q14)

- **One common frozen cohort** for both gates. All observed- and placebo-date support requirements are resolved **before any inference**; there are **no post-E1 exclusions** except correction of a formally documented data-integrity error (which reruns both gates). Every drop reason is counted.
- **Habitat-factor breadth:** each daily LOO factor observation requires **≥ 50** distinct PIT-eligible non-focal names with valid returns (membership fixed from information before the return interval). **Asymmetric handling:** a below-floor day *inside* the 252-session beta window is treated as **missing** (the ≥200-pair rule governs); **all 60 forward sessions** must clear the floor for a date to be admissible.
- **Placebo embargo:** a candidate placebo date is inadmissible when its 60-session forward window **intersects** (by tradable entry-session index, not calendar approximation) the forward window of **any** qualifying code-P insider event for that ticker — including events later dropped by real-event de-overlap. **Insider events only**; no earnings embargo in the primary (optional diagnostic).
- **Placebo sampling:** exactly **100 unique** admissible dates, **uniform without replacement**, **no minimum spacing**; each with its own strictly pre-date beta and the same PIT eligibility/beta/breadth/forward-window support. A cluster with **< 100 admissible dates** is excluded during common-cohort formation and counted.

### 6. Reproducibility contract (Q8, Q10, Q14, Q15)

- RNG: NumPy `Generator(PCG64)`. **E1, E2, and placebo streams are separated**, each seeded via a **frozen SHA-256 serialization** of `(master seed, specification version, gate tag)`; per-cluster placebo seeds add the immutable cluster identifier.
- The reproducibility manifest records: exact **NumPy major/minor version**, the generator, all derived seeds, the **data fingerprint**, the **bootstrap-index hash**, and the hash-serialization contract — so the frozen estimator and every draw are bit-reproducible cross-platform.

## Consequences

- E1/E2 verdicts are **not** comparable gate-by-gate to R2-1 / CMFT / Phase 2, nor to CFOB Stage D — a different statistical object with its own frozen protocol block.
- The divergences are **not** a loosening: the block bootstrap is strictly harder than parametric t on this dependence structure; the placebo + beta double-adjustment is strictly harder than raw excess; 25 bps round-trip is stricter than the 10 bps used elsewhere; α = 0.005 with `p=(1+K)/(B+1)` is a conservative one-sided bar; and the two gates are conjunctive.
- Prior lines stay settled. Nothing here reopens residual, R2-1, PEAD, or CMFT, and none of these bars may be back-ported to rescue them.
- Changing **any** frozen constant later is a **new trial** recorded against the deflated-Sharpe standard, not an edit to this one.
- A green E1 + green E2 authorizes exactly **one** predeclared next step (the characteristic-matched control named in ADR 0002, if pursued); it is **never** capital permission. `capital_go` stays a separate human decision.
