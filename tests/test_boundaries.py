import ast
import subprocess
from pathlib import Path

import pytest


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
                violations.extend(
                    f"{path}:{node.lineno}: import {name}" for name in imported if _forbidden(name)
                )
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
    assert (
        "live: calls the real Alpaca market-data API"
        in config["tool"]["pytest"]["ini_options"]["markers"]
    )


def test_paper_execute_marker_is_registered() -> None:
    import tomllib

    config = tomllib.loads(Path("pyproject.toml").read_text())
    assert (
        "paper_execute: submits a real paper order to Alpaca"
        in config["tool"]["pytest"]["ini_options"]["markers"]
    )


BANNED_BROKER_MODULES = {"invest.adapters.alpaca_broker"}
BANNED_BROKER_NAMES = {"AlpacaBroker", "BrokerFetchError", "BrokerPort"}


def _find_broker_references(tree: ast.AST, label: str) -> list[str]:
    """Walk `tree` for any reference to the banned broker module/names, including the
    evasive `from invest.adapters import alpaca_broker` + `alpaca_broker.AlpacaBroker(...)`
    pattern: a parent-package ImportFrom naming the submodule as an alias, and any
    ast.Attribute whose `.attr` matches a banned name regardless of the base object."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in BANNED_BROKER_MODULES:
            violations.append(f"{label}: import from {node.module}")
        elif isinstance(node, ast.ImportFrom) and node.module == "invest.adapters":
            violations.extend(
                f"{label}: import from invest.adapters import {alias.name}"
                for alias in node.names
                if alias.name == "alpaca_broker"
            )
        elif isinstance(node, ast.Import):
            violations.extend(
                f"{label}: import {alias.name}"
                for alias in node.names
                if alias.name in BANNED_BROKER_MODULES
            )
        elif isinstance(node, ast.Name) and node.id in BANNED_BROKER_NAMES:
            violations.append(f"{label}: references {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_BROKER_NAMES:
            violations.append(f"{label}: references .{node.attr}")
    return violations


def test_strengthened_broker_reference_checker_catches_module_attribute_evasion() -> None:
    """`from invest.adapters import alpaca_broker` then `alpaca_broker.AlpacaBroker(...)`
    produces an ast.Attribute node whose value is ast.Name(id='alpaca_broker') and an
    ast.ImportFrom whose module is the parent package `invest.adapters` -- neither is a
    bare `ast.Name` matching the old banned_names set, so the old check never caught it.
    The strengthened checker must flag both the module-import-as-attribute-access pattern
    and the `.attr` access itself."""
    snippet = (
        "from invest.adapters import alpaca_broker\n"
        "\n"
        "def build():\n"
        "    return alpaca_broker.AlpacaBroker()\n"
    )
    tree = ast.parse(snippet, filename="<synthetic>")
    violations = _find_broker_references(tree, "<synthetic>")
    assert violations != []


def test_strengthened_broker_reference_checker_has_no_false_positives_on_real_backtest_sources() -> (
    None
):
    """Regression guard: the strengthened check must not flag the actual backtest sources.
    backtest_run.py/backtest_metrics.py legitimately never reference alpaca_broker at all.
    cli.py DOES import AlpacaBroker/BrokerFetchError module-wide for `execute_main` (a
    separate, legitimate code path) -- so this checks only the backtest-scoped functions,
    exactly like the real boundary test does, not the whole cli.py module."""
    for path in (
        Path("src/invest/application/backtest_run.py"),
        Path("src/invest/domain/backtest_metrics.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert _find_broker_references(tree, str(path)) == []

    cli_path = Path("src/invest/adapters/cli.py")
    cli_tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    backtest_function_names = {"backtest_main", "_backtest_parser", "_backtest_report"}
    for node in ast.walk(cli_tree):
        if isinstance(node, ast.FunctionDef) and node.name in backtest_function_names:
            assert _find_broker_references(node, f"cli.py::{node.name}") == []


def test_backtest_code_path_never_imports_broker_or_references_brokerport() -> None:
    """The backtest replay path never touches the broker: mirrors the market-data adapter's
    hardcoded-paper-URL negative test, but for the day-0 replay harness/metrics/CLI.

    Uses the strengthened `_find_broker_references` checker so this stays consistent
    with `test_strengthened_broker_reference_checker_*` above: it also catches the
    `from invest.adapters import alpaca_broker` + `alpaca_broker.AlpacaBroker(...)`
    evasion, not just bare-Name references."""
    violations: list[str] = []

    for path in (
        Path("src/invest/application/backtest_run.py"),
        Path("src/invest/domain/backtest_metrics.py"),
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(_find_broker_references(tree, str(path)))

    cli_path = Path("src/invest/adapters/cli.py")
    cli_tree = ast.parse(cli_path.read_text(encoding="utf-8"), filename=str(cli_path))
    backtest_function_names = {"backtest_main", "_backtest_parser", "_backtest_report"}
    for node in ast.walk(cli_tree):
        if isinstance(node, ast.FunctionDef) and node.name in backtest_function_names:
            violations.extend(_find_broker_references(node, f"cli.py::{node.name}"))

    assert violations == [], "Backtest code path touches broker/BrokerPort:\n" + "\n".join(
        violations
    )


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


def test_market_context_flag_is_backtest_only_and_never_added_to_execute_parser() -> None:
    from invest.adapters.cli import _backtest_parser, _execute_parser

    backtest_options = {action.dest for action in _backtest_parser()._actions}
    execute_options = {action.dest for action in _execute_parser()._actions}

    assert "market_context" in backtest_options
    assert "market_context" not in execute_options


def test_strategy_flag_is_backtest_only_and_absent_from_execute_and_scan_parsers() -> None:
    from invest.adapters.cli import _backtest_parser, _execute_parser, _parser

    backtest_options = {action.dest for action in _backtest_parser()._actions}
    execute_options = {action.dest for action in _execute_parser()._actions}
    scan_options = {action.dest for action in _parser()._actions}

    assert "strategy" in backtest_options
    assert "strategy" not in execute_options
    assert "strategy" not in scan_options


def test_exit_policy_flag_is_backtest_only_and_absent_from_execute_and_scan_parsers() -> None:
    from invest.adapters.cli import _backtest_parser, _execute_parser, _parser

    backtest_options = {action.dest for action in _backtest_parser()._actions}
    execute_options = {action.dest for action in _execute_parser()._actions}
    scan_options = {action.dest for action in _parser()._actions}

    assert "exit_policy" in backtest_options
    assert "exit_policy" not in execute_options
    assert "exit_policy" not in scan_options


def test_phase2_admission_flags_are_backtest_only_and_absent_from_execute_and_scan() -> None:
    from invest.adapters.cli import _backtest_parser, _execute_parser, _parser

    backtest_options = {action.dest for action in _backtest_parser()._actions}
    execute_options = {action.dest for action in _execute_parser()._actions}
    scan_options = {action.dest for action in _parser()._actions}

    for flag in ("max_concurrent_positions", "admission_seed"):
        assert flag in backtest_options
        assert flag not in execute_options
        assert flag not in scan_options


def test_sharadar_source_is_backtest_only_and_protected_snapshot_data_is_ignored() -> None:
    from invest.adapters.cli import _backtest_parser, _execute_parser, _parser

    backtest_options = {action.dest for action in _backtest_parser()._actions}
    execute_options = {action.dest for action in _execute_parser()._actions}
    scan_options = {action.dest for action in _parser()._actions}
    assert "source" in backtest_options
    assert "source" not in execute_options
    assert "source" not in scan_options

    cli_tree = ast.parse(Path("src/invest/adapters/cli.py").read_text(encoding="utf-8"))
    backtest_functions = {"_backtest_parser", "backtest_main", "_backtest_report"}
    forbidden_functions = {"_parser", "main", "_execute_parser", "execute_main"}
    for node in ast.walk(cli_tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        references = {
            reference.id
            for reference in ast.walk(node)
            if isinstance(reference, ast.Name) and reference.id == "SharadarMarketDataReader"
        }
        if node.name in backtest_functions:
            continue
        if node.name in forbidden_functions:
            assert references == set()

    protected = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        check=False,
        capture_output=True,
        input="fixtures/snapshots/sharadar/bars.json\nbacktest.sqlite\n",
        text=True,
    )
    assert protected.stdout.splitlines() == [
        "fixtures/snapshots/sharadar/bars.json",
        "backtest.sqlite",
    ]


def test_sharadar_reader_name_is_isolated_to_the_backtest_dispatch() -> None:
    cli_tree = ast.parse(Path("src/invest/adapters/cli.py").read_text(encoding="utf-8"))
    source_flag_functions = {
        node.name
        for node in ast.walk(cli_tree)
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(value, ast.Constant) and value.value == "--source"
            for value in ast.walk(node)
        )
    }
    assert source_flag_functions == {"_backtest_parser"}

    reader_imports = [
        node
        for node in ast.walk(cli_tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "invest.adapters.sharadar_market_data"
        and any(alias.name == "SharadarMarketDataReader" for alias in node.names)
    ]
    assert len(reader_imports) == 1
    backtest_dispatch = next(
        node
        for node in cli_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "backtest_main"
    )
    assert reader_imports == [
        node
        for node in ast.walk(backtest_dispatch)
        if isinstance(node, ast.ImportFrom)
        and node.module == "invest.adapters.sharadar_market_data"
    ]

    protected_paths = (
        Path("src/invest/adapters/alpaca_broker.py"),
        Path("src/invest/application/execute_run.py"),
        Path("src/invest/application/scan_run.py"),
        Path("src/invest/domain/scanner.py"),
        Path("src/invest/domain/momentum_selection_scanner.py"),
    )
    for path in protected_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        references = [
            node
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Name)
                and node.id == "SharadarMarketDataReader"
                or isinstance(node, ast.ImportFrom)
                and node.module == "invest.adapters.sharadar_market_data"
                or isinstance(node, ast.Import)
                and any(
                    alias.name == "invest.adapters.sharadar_market_data" for alias in node.names
                )
            )
        ]
        assert references == [], f"Sharadar reader escaped backtest boundary: {path}"


# Sole allowed importer/caller of SharadarTickersReader / SharadarActionsReader.
_ALLOWED_REFERENCE_READER_CALLERS: frozenset[Path] = frozenset(
    {Path("src/invest/adapters/sharadar_context_source.py")}
)

_PROTECTED_REFERENCE_PATHS = (
    Path("src/invest/adapters/cli.py"),
    Path("src/invest/adapters/generate_context_cli.py"),
    Path("src/invest/adapters/backtest_context_json.py"),
    Path("src/invest/application/backtest_run.py"),
    Path("src/invest/application/execute_run.py"),
    Path("src/invest/application/scan_run.py"),
    Path("src/invest/application/generate_market_context.py"),
    Path("src/invest/domain/market_context.py"),
    Path("src/invest/adapters/alpaca_broker.py"),
)


def _find_reference_reader_references(
    tree: ast.AST, label: str, reader_name: str, module_name: str
) -> list[str]:
    module_parent, module_leaf = module_name.rsplit(".", 1)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module_name:
            violations.append(f"{label}: import from {module_name}")
        elif isinstance(node, ast.ImportFrom) and node.module == module_parent:
            violations.extend(
                f"{label}: import from {module_parent} import {alias.name}"
                for alias in node.names
                if alias.name == module_leaf
            )
        elif isinstance(node, ast.Import):
            violations.extend(
                f"{label}: import {alias.name}" for alias in node.names if alias.name == module_name
            )
        elif isinstance(node, ast.Name) and node.id == reader_name:
            violations.append(f"{label}: references {reader_name}")
        elif isinstance(node, ast.Attribute) and node.attr == reader_name:
            violations.append(f"{label}: references .{reader_name}")
    return violations


@pytest.mark.parametrize(
    ("reader_name", "module_name"),
    [
        ("SharadarTickersReader", "invest.adapters.sharadar_tickers"),
        ("SharadarActionsReader", "invest.adapters.sharadar_actions"),
    ],
)
def test_reference_guard_catches_direct_and_module_qualified_reader_references(
    reader_name: str, module_name: str
) -> None:
    module_parent, module_leaf = module_name.rsplit(".", 1)
    tree = ast.parse(
        f"from {module_parent} import {module_leaf}\n"
        f"from {module_name} import {reader_name}\n"
        f"{module_leaf}.{reader_name}()\n"
        f"{reader_name}()\n",
        filename="<synthetic>",
    )

    violations = _find_reference_reader_references(tree, "<synthetic>", reader_name, module_name)

    assert violations == [
        f"<synthetic>: import from {module_parent} import {module_leaf}",
        f"<synthetic>: import from {module_name}",
        f"<synthetic>: references .{reader_name}",
        f"<synthetic>: references {reader_name}",
    ]


def test_reference_reader_allowlist_is_exactly_context_source() -> None:
    assert _ALLOWED_REFERENCE_READER_CALLERS == frozenset(
        {Path("src/invest/adapters/sharadar_context_source.py")}
    )


@pytest.mark.parametrize(
    ("reader_name", "module_name"),
    [
        ("SharadarTickersReader", "invest.adapters.sharadar_tickers"),
        ("SharadarActionsReader", "invest.adapters.sharadar_actions"),
    ],
)
def test_reference_readers_are_isolated_from_all_protected_paths(
    reader_name: str, module_name: str
) -> None:
    """Default-deny tree scan; only the one-path allowlist may reference readers."""
    own_module = Path("src/invest") / f"{module_name.removeprefix('invest.').replace('.', '/')}.py"
    violations: list[str] = []
    for path in Path("src/invest").rglob("*.py"):
        if path == own_module or path in _ALLOWED_REFERENCE_READER_CALLERS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            _find_reference_reader_references(tree, str(path), reader_name, module_name)
        )
    assert violations == []


@pytest.mark.parametrize(
    ("reader_name", "module_name"),
    [
        ("SharadarTickersReader", "invest.adapters.sharadar_tickers"),
        ("SharadarActionsReader", "invest.adapters.sharadar_actions"),
    ],
)
def test_protected_cli_domain_and_backtest_paths_deny_reference_readers(
    reader_name: str, module_name: str
) -> None:
    violations: list[str] = []
    for path in _PROTECTED_REFERENCE_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            _find_reference_reader_references(tree, str(path), reader_name, module_name)
        )
    assert violations == []
    # CLI orchestrates via source only; consumers stay importable unchanged.
    cli_tree = ast.parse(Path("src/invest/adapters/generate_context_cli.py").read_text())
    imports = {
        n.module for n in ast.walk(cli_tree) if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "invest.adapters.sharadar_context_source" in imports
    assert "invest.application.backtest_run" not in imports
    from invest.adapters.backtest_context_json import BacktestContextJsonReader
    from invest.application.backtest_run import BacktestRun
    from invest.domain.market_context import MarketContext

    assert callable(BacktestContextJsonReader().load)
    assert callable(BacktestRun)
    assert callable(MarketContext)
