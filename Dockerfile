# ---- build stage: produce a wheel from the source tree ----
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS builder

WORKDIR /build
RUN pip install --no-cache-dir build

# Only the files needed to build the wheel (maximises layer caching).
COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m build --wheel --outdir /dist

# ---- runtime stage: install the wheel into a clean image ----
FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 AS runtime

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HUBSPOT_HOST=0.0.0.0 \
    HUBSPOT_PORT=8000

# OAuth (HTTP) mode listens on this port. Token (stdio) mode ignores it.
EXPOSE 8000

# Runtime configuration (see README): for oauth mode set HUBSPOT_AUTH_MODE=oauth,
# HUBSPOT_CLIENT_ID, HUBSPOT_CLIENT_SECRET, HUBSPOT_SERVER_URL.
CMD ["hubspot-mcp"]
