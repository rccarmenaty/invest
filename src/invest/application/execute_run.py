from collections import defaultdict
from datetime import date

from pydantic import BaseModel

from invest.adapters.alpaca_broker import BrokerFetchError
from invest.application.ports import BrokerPort, Journal
from invest.contracts.events import (
    ExecutionHalted,
    ExecutionSkipped,
    OrderIntentEvent,
    OrderRejected,
    OrderSubmitted,
)
from invest.domain.models import DailyBar, FixtureInputs, OrderIntent, ScanDecision
from invest.domain.scanner import MomentumScanner
from invest.domain.sizing import GateReason, compute_intent, evaluate_gates, evaluate_halt_gates


class ExecuteRun:
    """Compute journaled execution intents without mutating the broker."""

    def __init__(
        self,
        scanner: MomentumScanner,
        journal: Journal,
        broker: BrokerPort,
        rule_version: str,
    ) -> None:
        self._scanner = scanner
        self._journal = journal
        self._broker = broker
        self._rule_version = rule_version
        self.failed_reason: str | None = None

    def execute(self, inputs: FixtureInputs, *, execute: bool = False) -> list[BaseModel]:
        self.failed_reason = None
        snapshot = self._broker.snapshot()
        halt_reason = evaluate_halt_gates(snapshot)
        decisions = [decision for decision in self._scanner.scan(inputs.universe, inputs.bars) if decision.accepted]
        if halt_reason is not None:
            halt_date = decisions[0].decision_date if decisions else max(
                (bar.date for bar in inputs.bars), default=date.min
            )
            self._journal.append(
                ExecutionHalted.from_reason(
                    reason=halt_reason,
                    decision_date=halt_date,
                    fixture_version=inputs.universe.fixture_version,
                    rule_version=self._rule_version,
                )
            )
            for decision in decisions:
                self._journal.append(
                    ExecutionSkipped.from_reason(
                        intent_id_or_symbol=decision.symbol,
                        reason=halt_reason,
                        symbol=decision.symbol,
                        decision_date=decision.decision_date,
                        fixture_version=inputs.universe.fixture_version,
                        rule_version=self._rule_version,
                    )
                )
            return self._journal.events()

        by_symbol: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(inputs.bars, key=lambda item: (item.symbol, item.date)):
            by_symbol[bar.symbol].append(bar)

        open_position_count = snapshot.open_position_count
        deployed_value = snapshot.deployed_value
        available_buying_power = snapshot.buying_power
        for candidate_index, decision in enumerate(decisions):
            bars = by_symbol[decision.symbol]
            history = bars[:-1]
            intent, sizing_reason = compute_intent(
                decision.symbol,
                decision.decision_date,
                snapshot.equity,
                history,
                bars[-1].close,
                bars[-1].low,
            )
            intent_event = None
            if intent is not None:
                intent_event = OrderIntentEvent.from_intent(
                    intent,
                    fixture_version=inputs.universe.fixture_version,
                    rule_version=self._rule_version,
                )

            reason = evaluate_gates(
                intent,
                sizing_reason,
                snapshot,
                open_position_count,
                deployed_value,
                available_buying_power,
            )
            if reason is not None:
                self._journal.append(
                    ExecutionSkipped.from_reason(
                        intent_id_or_symbol=intent_event.event_id if intent_event else decision.symbol,
                        reason=reason,
                        symbol=decision.symbol,
                        decision_date=decision.decision_date,
                        fixture_version=inputs.universe.fixture_version,
                        rule_version=self._rule_version,
                    )
                )
                continue
            if intent is not None:
                self._journal.append(intent_event)
                if execute:
                    try:
                        opens_position = self._submit(intent_event, intent, decision, inputs)
                    except BrokerFetchError as error:
                        self.failed_reason = error.reason
                        self._journal.append(
                            ExecutionSkipped.from_reason(
                                intent_id_or_symbol=intent_event.event_id,
                                reason=error.reason,
                                symbol=decision.symbol,
                                decision_date=decision.decision_date,
                                fixture_version=inputs.universe.fixture_version,
                                rule_version=self._rule_version,
                            )
                        )
                        for remaining in decisions[candidate_index + 1 :]:
                            self._journal.append(
                                ExecutionSkipped.from_reason(
                                    intent_id_or_symbol=remaining.symbol,
                                    reason=error.reason,
                                    symbol=remaining.symbol,
                                    decision_date=remaining.decision_date,
                                    fixture_version=inputs.universe.fixture_version,
                                    rule_version=self._rule_version,
                                )
                            )
                        break
                    if opens_position:
                        open_position_count += 1
                        notional = intent.qty * intent.entry
                        deployed_value += notional
                        available_buying_power -= notional
                else:
                    open_position_count += 1
                    deployed_value += intent.qty * intent.entry

        return self._journal.events()

    def _submit(
        self,
        intent_event: OrderIntentEvent,
        intent: OrderIntent,
        decision: ScanDecision,
        inputs: FixtureInputs,
    ) -> bool:
        ack = self._broker.submit_bracket(intent, client_order_id=intent_event.client_order_id)
        common = dict(
            symbol=decision.symbol,
            decision_date=decision.decision_date,
            fixture_version=inputs.universe.fixture_version,
            rule_version=self._rule_version,
        )
        if ack.status == "submitted":
            self._journal.append(
                OrderSubmitted.from_ack(
                    intent_id=intent_event.event_id,
                    broker_order_id=ack.broker_order_id or "",
                    **common,
                )
            )
            return True
        elif ack.status == "already-submitted":
            self._journal.append(
                ExecutionSkipped.from_reason(
                    intent_id_or_symbol=intent_event.event_id,
                    reason=GateReason.ALREADY_SUBMITTED,
                    broker_order_id=ack.broker_order_id or "",
                    **common,
                )
            )
            return True
        else:
            self._journal.append(
                OrderRejected.from_ack(
                    intent_id=intent_event.event_id,
                    reason=ack.reason or "rejected",
                    broker_order_id=ack.broker_order_id or "",
                    **common,
                )
            )
            return False
