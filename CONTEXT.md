# Invest research context

Ubiquitous language for the point-in-time equity research program (signals, structure tests, promotion gates). Not implementation.

## Language

### Research outcomes

**Promotion block**:
A published negative on *accept-for-promotion* under frozen gates. Residual research may continue only under a single predeclared next experiment. Does not assert that the underlying signal is dead.
_Avoid_: program kill, structure dead, full reject (unless those terms are chosen explicitly)

**Program kill**:
End of a research line (e.g. long-hold naïve/Core portfolio). No residual experiments on that line; next budget is pivot or pause only.
_Avoid_: promotion block, temporary NO-GO

**NO-GO**:
Frozen-gate failure that blocks promotion of the tested configuration. Always pair with the failing gate name (e.g. year concentration).
_Avoid_: “failed” without naming which gate

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
After a residual experiment settles, the default next budget is research pause on that line. Form-4 audit or a new PRD requires an explicit re-open, not auto-start from a green or red residual report.
_Avoid_: automatic Form-4, silent ranking reopen
