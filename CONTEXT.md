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

### Form-4 / CMP

**Purchase cluster**:
≥2 distinct insiders of one issuer with qualifying open-market purchases whose trade dates fall inside a frozen window (CFOB primary object on #76). Settled **kill_line** at E1 on year-concentration; not the CMP baseline object.
_Avoid_: opportunistic purchase (different object), “Form-4 signal” (ambiguous)

**Opportunistic purchase**:
A point-in-time CMP-classified non-routine open-market (code P) non-derivative insider purchase that clears frozen size, staleness, and habitat filters. Primary event object for the CMP baseline re-open.
_Avoid_: purchase cluster, all Form-4 buys, routine purchase as primary

**Routine insider (CMP)**:
An insider who traded in each of the prior three years and traded in the same calendar month in those three years; classification uses only history available before the evaluation trade. Routine purchases are a **negative-control diagnostic**, not the primary claim.
_Avoid_: “scheduled 10b5-1 only”, silent primary flip when routine share is high

**CMP baseline**:
Unconditional event study on opportunistic purchases with frozen entry, horizon, costs, placebo, and year-share gates — **before** any ranking, GP, or symbolic search over features.
_Avoid_: GP-rescued Form-4, cluster E1 re-cut, implementability as research verdict
