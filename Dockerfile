FROM ghcr.io/astral-sh/uv:0.6.11-python3.12-bookworm-slim@sha256:0ddac20e6ed02c16bc5f3881619d4ef959427f2ffbe246db87b375b133523be3

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY fixtures ./fixtures
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["invest-scan"]
CMD ["--universe", "fixtures/v1/universe.json", "--bars", "fixtures/v1/bars.json", "--format", "json"]
