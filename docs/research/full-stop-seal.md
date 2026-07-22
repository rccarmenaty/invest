# Full-Stop seal — CS alpha research budget

**Date:** 2026-07-21  
**Authority:** Human grill after Round 2 meta-judge program + R2-1 / PEAD F0 measurements  
**ADR:** `docs/adr/0001-full-stop-cs-alpha.md`  
**Glossary:** `CONTEXT.md` — **Full-Stop**, **honest liquid beta**, **non-claim engineering**, **event-only re-open**

## Decision

**Full-Stop** on cross-sectional alpha research.

| Axis | Call |
| --- | --- |
| Strength | Program-level budget kill (not pause-default) |
| Residual | Hard freeze / narrow freeze (unchanged) |
| R2-1 xs-reversal | Settled **kill_line** (`docs/research/xs-reversal-results.md`) |
| PEAD F0 | Settled **kill_line** (`docs/research/pead-f0-results.md`) |
| CMFT Stage A | Event-only re-open #74 dual-exited **underpowered-stop** (`docs/research/cmft-results.md`); T1 not trained; **not** a tree-edge falsification |
| Form-4 clusters (CFOB) | Event-only re-open #76 settled **kill_line** at E1 on year-concentration (PR #78); cluster object frozen dead |
| Form-4 CMP opportunistic | **Event-only re-open authorised** 2026-07-22 — baseline only, SEC tape, no SF1/SF2; see ADR `0003` + active PRD issue; GP deferred |
| Capital | **Honest liquid beta** only while no implementability_eligible line exists |
| Allowed | Active authorised re-open work; otherwise **non-claim engineering** only |
| Forbidden | Cluster E1 rescue; PEAD tape-for-alpha; residual rescue / ranking / DAMB; CMFT T1 on #74; GP on real Form-4 targets before CMP baseline stage_pass; curiosity re-runs; threshold retuning; SF1/SF2 required framing for CMP |
| End condition | Dual-exit on active re-open → Full-Stop default resumes; else new PRD + grill |

## Why (short)

Two sequential funded lines after residual_hope DIE failed cleanly: R2-1 on signal gates; PEAD F0 on data-object absence (fail-closed). Paying further engineering tax for fundamentals or ownership tapes without a new human re-open repeats the “build before honest stop” trap. Full-Stop is a success mode for research process, not a temporary mood.

### Event-only re-open log (append-only)

| Event | PRD | Outcome | Date |
| --- | --- | --- | --- |
| Full-Stop seal | — | CS alpha budget ended | 2026-07-21 |
| CMFT Stage A | #74 | **underpowered-stop** (full-depth SEP 1998–2025; K0 fail; T1 skipped); loop closed | 2026-07-21 |
| CFOB E1 (clusters) | #76 | **kill_line** — year-concentration (2009 ≈ 31% of positive contribution); placebo/trimmed/SPY passed; PR #78 | 2026-07-22 |
| CMP opportunistic baseline | **#79** | **re-open authorised** — SEC tape only; CMP baseline before GP; ADR 0003 | 2026-07-22 |

After a dual-exit on an event-only re-open, **Full-Stop default resumes** until the next new PRD + grill. Settled non-claims on #74: do not narrate “trees have no edge.” Settled on #76: do not re-litigate purchase **clusters** or retune E1 year-share.

## Not decided here

- Specific beta vehicle, broker, or tax lot implementation (productization, not alpha research).
- Whether a future re-open may re-litigate settled residual / R2-1 / PEAD nulls (default: do not; new PRD must say so explicitly).
- Whether a future re-open may amend CMFT K0 (50 bps MDS) or train T1 under a different power object (requires **new** PRD, not re-use of #74).
