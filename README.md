# invest

Deterministic, signals-only momentum scanner using validated local fixtures. This
foundation does not connect to brokers or provision infrastructure.

## Local scan

```sh
uv run invest-scan \
  --universe fixtures/v1/universe.json \
  --bars fixtures/v1/bars.json \
  --format json
```

## Verify

```sh
uv run --extra dev pytest
uv run --extra dev ruff check .
```

## Container

```sh
docker build -t invest-scan .
docker run --rm invest-scan
```

The image packages only the application and fixtures. Kubernetes, Helm, cluster
provisioning, and live-trading configuration are intentionally out of scope.
