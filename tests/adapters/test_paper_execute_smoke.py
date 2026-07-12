import os

import pytest

from invest.adapters.alpaca_broker import AlpacaBroker
from invest.adapters.cli import execute_main

_REQUIRES_CREDS = pytest.mark.skipif(
    not os.environ.get("ALPACA_API_KEY_ID"), reason="requires Alpaca paper credentials"
)


@pytest.mark.paper_execute
@_REQUIRES_CREDS
def test_paper_execute_snapshot_is_read_only_smoke() -> None:
    """Real paper-account GETs only; asserts the connection/mapping works, mutates nothing."""
    snapshot = AlpacaBroker().snapshot()
    assert snapshot.equity >= 0


@pytest.mark.paper_execute
@_REQUIRES_CREDS
def test_paper_execute_cli_dry_run_smoke() -> None:
    """Full dry-run CLI invocation against the real paper API; never submits an order."""
    result = execute_main(
        [
            "--universe",
            "fixtures/v1/universe.json",
            "--bars",
            "fixtures/v1/bars.json",
            "--format",
            "json",
        ]
    )
    assert result in (0, 2)
