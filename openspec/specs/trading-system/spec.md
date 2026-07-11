# Trading System Specification

This main OpenSpec spec is scaffolded from `SPEC.md` and should be treated as the current source seed until later SDD changes refine individual requirements.

## Overview

Build a paper-first swing-trading system that detects confirmed momentum breakouts, sizes positions mechanically, submits protected bracket orders, and proves expectancy through replay/backtest plus paper trading before any live key is used.

## Core Requirements

### Requirement: Paper-first validation gates
The system MUST run through signals-only, replay/backtest, paper loop, live-readiness rehearsal, and live-small phases in order. Live trading MUST NOT occur until replay and paper expectancy gates pass.

### Requirement: Authoritative daily decisions
Candidate promotion, relative volume, breakout checks, ATR, and moving average decisions MUST use consolidated/SIP daily bars or delayed consolidated historical bars. IEX-only intraday data MAY be used for awareness only unless explicitly configured as a degraded-data experiment.

### Requirement: Momentum signal confirmation
The system MUST detect spike candidates on daily close, then require day +1/+2 confirmation before emitting entry signals. It MUST reject or hold candidates when earnings data is missing or unsafe.

### Requirement: Mechanical risk and order safety
Risk per trade MUST be 1% of account equity, max concurrent positions MUST be 5, max deployed equity MUST be 25%, and a 3% intraday drawdown MUST halt new entries. Broker/account restrictions MUST be read from Alpaca/account state rather than hard-coded PDT assumptions.

### Requirement: Hexagonal event-driven services
Each service MUST keep pure domain logic separate from adapters and SDKs. NATS JetStream events and Pydantic contracts are the API between services, and consumers MUST be idempotent for at-least-once delivery.

### Requirement: Replay and observability
Every trading day MUST be replayable from persisted events and historical point-in-time data. Journal, rejection reasons, data freshness, broker mismatches, and risk halts MUST be observable.

## Source

Seeded from `/Users/rcty/invest/SPEC.md` on 2026-07-11. Keep SPEC.md available as the detailed narrative until SDD deltas replace or expand this main spec.
