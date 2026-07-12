import ast
from pathlib import Path


FORBIDDEN_IMPORT_ROOTS = {
    "alpaca",
    "httpx",
    "invest.adapters",
    "invest.application",
    "nats",
    "psycopg",
    "random",
    "requests",
    "socket",
    "sqlalchemy",
    "urllib",
}
FORBIDDEN_WALL_TIME_CALLS = {"datetime.now", "datetime.utcnow", "date.today"}


def test_domain_has_no_outward_dependencies_or_nondeterministic_calls() -> None:
    violations: list[str] = []
    for path in sorted(Path("src/invest/domain").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
                violations.extend(f"{path}:{node.lineno}: import {name}" for name in imported if _forbidden(name))
            elif isinstance(node, ast.ImportFrom) and node.module and _forbidden(node.module):
                violations.append(f"{path}:{node.lineno}: from {node.module}")
            elif isinstance(node, ast.Call):
                call_name = _call_name(node.func)
                if call_name in FORBIDDEN_WALL_TIME_CALLS or call_name in {"open", "eval", "exec"}:
                    violations.append(f"{path}:{node.lineno}: call {call_name}")

    assert violations == [], "Forbidden domain dependencies:\n" + "\n".join(violations)


def _forbidden(module: str) -> bool:
    return any(module == root or module.startswith(f"{root}.") for root in FORBIDDEN_IMPORT_ROOTS)


def _call_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def test_domain_boundary_explicitly_forbids_market_data_dependencies() -> None:
    assert {"httpx", "alpaca"} <= FORBIDDEN_IMPORT_ROOTS


def test_live_marker_is_registered() -> None:
    import tomllib
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert "live: calls the real Alpaca market-data API" in config["tool"]["pytest"]["ini_options"]["markers"]


def test_paper_execute_marker_is_registered() -> None:
    import tomllib
    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        "paper_execute: submits a real paper order to Alpaca"
        in config["tool"]["pytest"]["ini_options"]["markers"]
    )


def test_backtest_code_path_never_imports_broker_or_references_brokerport() -> None:
    """The backtest replay path never touches the broker: mirrors the market-data adapter's
    hardcoded-paper-URL negative test, but for the day-0 replay harness/metrics/CLI."""
    banned_modules = {"invest.adapters.alpaca_broker"}
    banned_names = {"AlpacaBroker", "BrokerFetchError", "BrokerPort"}
    violations: list[str] = []

    for path in (
        Path("src/invest/application/backtest_run.py"),
        Path("src/invest/domain/backtest_metrics.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in banned_modules:
                violations.append(f"{path}: import from {node.module}")
            elif isinstance(node, ast.Import):
                violations.extend(
                    f"{path}: import {alias.name}" for alias in node.names if alias.name in banned_modules
                )
            elif isinstance(node, ast.Name) and node.id in banned_names:
                violations.append(f"{path}: references {node.id}")

    cli_path = Path("src/invest/adapters/cli.py")
    cli_tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    backtest_function_names = {"backtest_main", "_backtest_parser", "_backtest_report"}
    for node in ast.walk(cli_tree):
        if isinstance(node, ast.FunctionDef) and node.name in backtest_function_names:
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name) and inner.id in banned_names:
                    violations.append(f"cli.py::{node.name}: references {inner.id}")

    assert violations == [], "Backtest code path touches broker/BrokerPort:\n" + "\n".join(violations)


def test_out_of_scope_guard_no_gap_strategy_confirmation_module_or_live_trading_url() -> None:
    """Reconcile item 1: gap-trading (rejected Named Decision 3) and confirmation-service
    (out of scope per Named Decision 1) must never materialize as strategy modules, and the
    new backtest files must never contain a non-paper Alpaca URL string."""
    violations: list[str] = []

    for path in Path("src/invest").rglob("*.py"):
        stem = path.stem.lower()
        if "gap" in stem:
            violations.append(f"gap-trading strategy module suspected: {path}")
        if "confirmation" in stem:
            violations.append(f"confirmation-service module suspected: {path}")

    backtest_files = (
        Path("src/invest/application/backtest_run.py"),
        Path("src/invest/domain/backtest_metrics.py"),
        Path("src/invest/adapters/cli.py"),
    )
    for path in backtest_files:
        text = path.read_text(encoding="utf-8")
        if '"https://api.alpaca.markets' in text or "'https://api.alpaca.markets" in text:
            violations.append(f"non-paper Alpaca URL string found in {path}")

    assert violations == [], "Out-of-scope guard violated:\n" + "\n".join(violations)
