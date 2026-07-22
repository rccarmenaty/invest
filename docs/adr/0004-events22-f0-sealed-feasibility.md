# EVENTS-22 starts with a sealed F0 feasibility audit

GitHub issue #81 reopens the announcement-reaction line for SHARADAR/EVENTS code
22, interpreted as Results of Operations / Item 2.02. The provider input is
date-granular, so the known-time rule is deliberately conservative: normalize
to the first trading session on or after the event date, use D+2 open as the
future primary entry, and retain D+1 open only as a future secondary check.

## Decision

Implement F0 only. F0 may inspect event identities and dates, point-in-time
listing facts, eligibility price and volume levels, session counts, and a
pre-existing variance/dependence basis. It must not accept or calculate event
reactions or forward returns.

The canonical unit is issuer × normalized known date. Duplicate/co-filing rows
are coalesced with their raw row identifiers retained. Events then use a
first-wins issuer de-overlap through the D+2/h60 primary horizon. The eligible
universe is point-in-time US primary common stock with price at least $5,
20-session median dollar volume at least $10 million, and at least 252 prior
valid sessions.

Annual folds use strictly prior information and become usable only with at
least two prior calendar years and 1,000 prior eligible events. F0 power is
frozen at 80% for a +1% effect and may use only a hashed variance/dependence
basis that predates EVENTS-22 outcome inspection. D+2/h60 is primary; D+1/h60
and h20 remain declared diagnostics for a possible E1.

## Consequences

- Any integrity-gate failure produces `kill_line`.
- Insufficient power produces `underpowered_stop`.
- A clean feasibility result produces `f0_pass` and stops at
  `awaiting_human_approval`; it does not start E1.
- Every artifact is deterministic and self-hashed, includes a raw-row decision
  ledger, says `capital_go=false`, and says `returns_measured=false`.
- The F0 driver rejects unknown manifest fields, making accidental reaction or
  forward-return inputs a hard failure.
- E1 has an executable refusal seam. A separate human approval and separate
  implementation are required before any outcome measurement.
