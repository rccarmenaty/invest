from typing import get_type_hints

from pydantic import BaseModel

from invest.application import ports
from invest.domain.models import AccountSnapshot, BrokerAck, OrderIntent


def test_broker_port_and_journal_accept_execution_contracts() -> None:
    assert get_type_hints(ports.BrokerPort.snapshot)["return"] is AccountSnapshot
    assert get_type_hints(ports.BrokerPort.find_order)["client_order_id"] is str
    submit_hints = get_type_hints(ports.BrokerPort.submit_bracket)
    assert submit_hints["intent"] is OrderIntent
    assert submit_hints["client_order_id"] is str
    assert submit_hints["return"] is BrokerAck
    assert get_type_hints(ports.Journal.append)["event"] is BaseModel
