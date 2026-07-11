import json
from pathlib import Path
import shutil
import subprocess

import pytest


PINNED_UV_IMAGE = (
    "ghcr.io/astral-sh/uv:0.6.11-python3.12-bookworm-slim"
    "@sha256:0ddac20e6ed02c16bc5f3881619d4ef959427f2ffbe246db87b375b133523be3"
)


def test_container_exposes_cli_without_cluster_assets() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert dockerfile.startswith(f"FROM {PINNED_UV_IMAGE}\n")
    assert 'ENTRYPOINT ["invest-scan"]' in dockerfile
    assert "kubectl" not in dockerfile.lower()
    forbidden = {"chart.yaml", "helmfile.yaml", "kustomization.yaml"}
    assert not any(path.name.lower() in forbidden for path in Path(".").rglob("*"))


def test_container_entrypoint_runs_the_default_scan(tmp_path: Path) -> None:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("Docker unavailable; container runtime acceptance was not executed")

    image = "invest-entrypoint-smoke:test"
    subprocess.run(
        [docker, "build", "--tag", image, "."],
        check=True,
        cwd=Path.cwd(),
        text=True,
    )
    result = subprocess.run(
        [docker, "run", "--rm", image],
        check=True,
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert payload
    assert payload[0]["event_type"] == "candidate.rejected.v1"
