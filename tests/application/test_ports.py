from typing import get_type_hints

from pydantic import BaseModel

from invest.application import ports
from invest.domain.models import AccountSnapshot, OrderIntent


def test_broker_port_and_journal_accept_execution_contracts() -> None:
    assert get_type_hints(ports.BrokerPort.snapshot)["return"] is AccountSnapshot
    assert get_type_hints(ports.BrokerPort.find_order)["client_order_id"] is str
    assert get_type_hints(ports.BrokerPort.submit_bracket)["intent"] is OrderIntent
    assert get_type_hints(ports.Journal.append)["event"] is BaseModel
