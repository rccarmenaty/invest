# Invest research context

Ubiquitous language for the point-in-time equity research program (signals, structure tests, promotion gates). Not implementation.

## Language

### Research outcomes

**Promotion block**:
A published negative on *accept-for-promotion* under frozen gates. Residual research may continue only under a single predeclared next experiment. Does not assert that the underlying signal is dead.
_Avoid_: program kill, structure dead, full reject (unless those terms are chosen explicitly)

**Program kill**:
End of a single research line (e.g. long-hold naïve/Core portfolio, R2-1 xs-reversal, PEAD under a given protocol). No residual experiments on *that* line; does not by itself end all CS alpha research.
_Avoid_: promotion block, temporary NO-GO, Full-Stop (broader)

**Full-Stop**:
End of the CS alpha research budget after settled line kills. No new cross-sectional alpha lines (residual rescue, PEAD tape-for-alpha, Form-4 F0, ranking theater) until event-only re-open. Capital default is honest liquid beta; only non-claim engineering continues.
_Avoid_: pause-default, soft pause, program kill (line-scoped), temporary NO-GO

**NO-GO**:
Frozen-gate failure that blocks promotion of the tested configuration. Always pair with the failing gate name (e.g. year concentration).
_Avoid_: “failed” without naming which gate

**Honest liquid beta**:
Production capital allocation to liquid passive/market exposure without a CS alpha claim. Not a backtested signal product and not residual packaging.
_Avoid_: TSMOM-as-alpha, paper CS books, capital_go on research lines

**Non-claim engineering**:
Providers, tooling, fixtures, CI, and docs that do not create an accept path or re-litigate settled research results.
_Avoid_: curiosity re-runs, threshold retuning, “just one more” gate rescue

### Experiments

**Structure test**:
Portfolio experiment that fixes entry event and varies hold/exit/admission only — not ranking science. Phase 2 is a structure test.
_Avoid_: strategy backtest (ambiguous), ranking test

**Year concentration**:
Share of total after-cost net profit attributable to a single calendar entry-year fold. Predeclared promotion limit ~25%.
_Avoid_: regime risk (broader), drawdown (path metric)

**FC-segregated book**:
Trade P&L after removing context/corporate-action forced closes from the alpha claim.
_Avoid_: clean book, alpha book (unless defined)

### Insider events

**Purchase cluster**:
Two or more distinct insiders of one issuer making non-derivative code-P purchases whose *trade* dates fall inside a 30-calendar-day window. The unit of the CFOB hypothesis.
_Avoid_: insider buy (a single trade), Form-4 event (a filing, not a cluster)

**Cluster known-time**:
The latest filing date among a cluster's purchases — the first moment the whole cluster is public. Entry is the next trading day's open. Filing date is day-granular; the insider tape carries no acceptance timestamp, so this is deliberately conservative.
_Avoid_: formation date (means the cross-sectional sort date), transaction date, acceptance datetime (does not exist on this tape)

**Staleness cap**:
Rejection of a purchase filed more than 10 calendar days after its trade date. The statutory deadline is two business days; the cap drops stale catch-up filings whose news is long since priced.
_Avoid_: late-filing flag alone (a reported attribute, not the rule)

**De-overlapped cohort**:
The first-wins event set: once a ticker produces a cluster it cannot re-enter until its measurement horizon closes. Prevents one firm entering repeatedly on overlapping windows, which would inflate significance. Density floors bind on this count.
_Avoid_: raw cluster count (reported, never gated on)

**Placebo null**:
The within-ticker date-shuffled distribution that an observed event excess is measured *against*. The primary statistic is the difference between observed and placebo mean — not the raw excess, because event cohorts can drift for cohort reasons alone.
_Avoid_: placebo gate (the weaker sanity-check sense used in R2-1 and CMFT)

**Common frozen cohort**:
The single event set that *both* E1 and E2 are measured on. It is the de-overlapped cohort further restricted, **before any inference**, to clusters that satisfy every point-in-time support requirement for both the observed and the placebo legs. The leave-one-out habitat factor requires **≥50** distinct PIT-eligible non-focal names (membership fixed from information before each return interval) for a factor observation to exist. Breadth failures are handled asymmetrically: a thin day *inside* the 252-session pre-known-time beta window merely yields a **missing** paired observation — the date stays estimable as long as **≥200** valid focal↔factor pairs remain (no imputation, no backward extension) — whereas **all 60 forward sessions** must clear the breadth floor for a date to be admissible. Each cluster must also have ≥100 unique admissible placebo dates (100 sampled without replacement under the frozen seed), each placebo date independently meeting the same habitat, beta-support, breadth and forward-window rules with its own strictly pre-date beta. Eligibility is resolved once and frozen; E1 and E2 never run on different event sets, and there is no post-E1 exclusion (except correction of a formally documented data-integrity error, which reruns both gates). Every drop reason is counted. Below a **2,000-cluster operational floor**, applied once to the final common cohort before either statistic is inspected, both E-stages return **`underpowered_stop`** and no gate statistic or p-value is attempted — an admissibility floor, not a proof of statistical power (which also depends on calendar spread, crisis concentration, `dᵢ` dispersion and the block structure, all reported as diagnostics).
_Avoid_: E1-on-full-cohort then E2-on-subset, excluding clusters after a gate runs, imputing missing returns, extending the estimation window to rescue support, treating the 2,000 floor as a power guarantee

**Placebo embargo**:
The rule that keeps real insider-timing information out of the placebo null. A within-ticker placebo candidate date is inadmissible when its frozen 60-session forward window — measured by **tradable entry-session index**, not a calendar-day approximation — intersects the forward window of *any* qualifying code-P insider event for that ticker, **including events later dropped by real-event de-overlap** (they still carry real signal). Insider events only; no earnings or other corporate-event embargo in the primary (optional diagnostic). Remaining admissible dates are sampled uniformly without replacement (exactly 100 unique per cluster, deterministic per-cluster hashed seed, no minimum spacing).
_Avoid_: embargoing only the focal cluster, calendar-day ±window approximation, earnings embargo in the primary, letting a real event window contaminate the null

**E1 residual-drift gate**:
First returns gate of the CFOB line. Primary statistic = observed h60 open-to-open net return (25 bps round-trip) minus the within-ticker placebo mean, on the [common frozen cohort](#common-frozen-cohort). Isolates whether the cluster's *timing* beat random timing in the same name; removes the ticker's unconditional drift but **not** same-window market movement. **Necessary, not sufficient**: a green E1 advances the line to E2 and authorizes nothing else — it cannot by itself validate alpha, and `capital_go` stays false by construction. A red E1 is a Promotion block naming the failing bar (the E1 primary gate statistic), or a Program kill. The controlling test is the [E1 primary gate](#e1-primary-gate-block-bootstrap), not a parametric t.
_Avoid_: alpha validation, capital permission, portfolio go-live, structure stage, Gate-1a (raw excess, weaker null)

**E1 primary gate (block bootstrap)**:
The controlling E1 test. The within-ticker placebo layer is computed **once**, collapsing each cluster to `dᵢ = Rᵢ,obs^net − mean(Rᵢ,placebo^net)`. Let `θ̂ = T(d)` be the full frozen winsorized (1/99) trimmed cohort statistic — an **equal-weight** average over clusters (each cluster one vote; no capitalization, liquidity, volatility, beta-precision or placebo-precision weighting). The primary estimand is the average effect across qualifying clusters; equal-calendar-month weighting is a diagnostic only. The null is imposed by recentering: `dᵢ⁰ = dᵢ − θ̂`. A **stationary block bootstrap** is then applied to the complete known-time calendar-month sequence: the calendar month is the resample unit, all observations in a selected month are carried together, contiguous months are drawn in random-length blocks (empty months preserved), so cross-ticker dependence and the dependence from overlapping 60-session holding windows are both retained. The full frozen statistic is recomputed on every replication; placebo dates are **not** redrawn inside replications. Finite-placebo-simulation sensitivity is assessed off-gate across frozen independent placebo seeds or by raising the placebo-draw count. IID and calendar-month-clustered t-statistics are reported as diagnostics only and never control the gate; ticker clustering is additionally reported when the frozen cohort repeats a ticker. **Gate rule:** one-sided, `p = (1 + K)/(B + 1)` where K is the count of replications whose frozen cohort statistic is ≥ the observed statistic; the gate passes iff `p ≤ α` (α and the bootstrap constants — block length, q, B, seed, cost ladder — are frozen in ADR 0003). The **line** advances only if *both* E1 and E2 clear their gate at 25 bps; neither gate filters individual clusters.
_Avoid_: parametric clustered-t as the gate, iid t as primary, single-month (non-block) resampling, per-ticker block as primary, redrawing placebo dates inside bootstrap replications, p = K/B (must be (1+K)/(B+1))

**E2 benchmark-residualized gate**:
Final research-acceptance gate for the CFOB line — a **habitat-factor-adjusted timing test**, explicitly *not* unrestricted asset-pricing alpha and *not* an investable portfolio return. The factor is the **leave-one-out** equal-weight return of the point-in-time eligible CFOB habitat (focal ticker excluded, so no self-inclusion). For every observed *and* placebo entry date the focal ticker's beta to that factor is estimated by OLS from a frozen **pre-entry** daily open-to-open estimation window; the 60-session focal net return is residualized against a beta-implied benchmark that **compounds the beta-scaled daily habitat return** (`∏(1+β̂·hₛ)−1`, beta applied per daily return *before* compounding — not one beta on the compounded factor) with **no intercept term**, identically on every placebo date. The habitat factor is gross; costs apply only to the focal leg. Intercept-inclusive and log-return variants are diagnostics. Each cluster collapses to `d_i^E2 = resid_obs − mean(resid_placebo)`, and the frozen cohort is evaluated under the *same* null-imposed stationary calendar-block bootstrap gate as E1 (`p ≤ α` at 25 bps). Statistic S_E2 thus removes both the ticker's unconditional drift (placebo leg) and same-window habitat-factor movement (date-specific beta), without crude double subtraction. Unit-beta habitat subtraction and SPY-based specs are diagnostics only. Only a green E2 completes research acceptance; even then `capital_go` remains a separate human decision.
_Avoid_: unrestricted/asset-pricing alpha, investable portfolio return, fixed beta-1 as primary, crude double subtraction (return − universe − placebo), self-inclusion in the habitat factor, treating a green E1 as sufficient

### Selection

**Random admission**:
Seeded lottery among same-session candidates when slots bind. Control for structure without a ranker.
_Avoid_: ranking, selection alpha

**Gate 1a**:
h60 excess return vs same-date eligible-universe mean on the event cohort (clustered inference). Diagnostic on residual drift, not a portfolio go-live gate.
_Avoid_: Phase 2, portfolio edge

**Concentration autopsy**:
Single residual measurement after a year-concentration promotion block: leave-dominant-year-out expectancy plus matched-exposure market context on the frozen structure book. Does not reopen ranking or change exit policy.
_Avoid_: re-optimization, Phase 3 ranking, DAMB package

**Economic residual bar (K2)**:
Residual price-event portfolio hope dies if leave-dominant-year mean after-cost expectancy is ≤ half the frozen full-book mean, or ≤ 0, or remaining walk-forward folds fail majority > 0, or matched equity exposure is not beaten after costs on the same windows. Survival is never promotion.
_Avoid_: mean > 0 alone, moving the year-concentration promotion gate

**Trade-window equity match (S2)**:
For each closed trade, apply the liquid equity proxy (SPY) open-to-open return over that trade’s entry-fill → exit-fill window to the trade’s notional; compare after-cost trade P&L to that matched proxy P&L. Same clock as the structure hold, not calendar buy-and-hold.
_Avoid_: calendar SPY buy-hold as primary kill metric, IWM-by-default

**Pause-default**:
After a residual experiment settles, the default next budget is research pause on that line. Form-4 audit or a new PRD requires an explicit re-open, not auto-start from a green or red residual report. Superseded for the Round 2 queue by Full-Stop once R2-1 and PEAD F0 both published kill_line.
_Avoid_: automatic Form-4, silent ranking reopen, Full-Stop (use when the whole CS budget ends)

**Hard freeze**:
Research-adjacent spend on the frozen claim is forbidden until re-open. Non-claim engineering may continue under Full-Stop and under line freezes.
_Avoid_: soft pause, “curiosity” re-runs as research

**Narrow freeze**:
Freeze applies only to the settled residual claim (here: naïve event → fixed-horizon → slot-lottery portfolio residual). A different signal family is a new line, not a continuation — except under Full-Stop, when new CS lines are also forbidden without event-only re-open.
_Avoid_: program-wide freeze as a synonym for residual freeze; Full-Stop (budget-level)

**Event-only re-open**:
Hard freeze, Full-Stop, or a line program kill ends only on an explicit human decision (new PRD + grill, or written re-open with named hypothesis). No calendar review, no auto-start from new data entitlement alone, no silent agent restart.
_Avoid_: check-back-Friday, silent agent restart, “we have SF1 now”
