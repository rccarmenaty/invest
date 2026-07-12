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
