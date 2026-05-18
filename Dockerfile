# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /build

# UV_COMPILE_BYTECODE: generate .pyc files at build time so the first import
# in the container doesn't stall on compilation.
# UV_LINK_MODE=copy: uv hard-links from its cache by default; hard-linking
# across block devices (always true in multi-stage builds) fails with EXDEV.
# UV_PROJECT_ENVIRONMENT: fixed venv path so the COPY in stage 2 is deterministic.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# ── Layer 1: dependencies only (cached until uv.lock changes) ───────────────
COPY pyproject.toml uv.lock ./
RUN uv sync \
        --frozen \
        --no-dev \
        --no-install-project

# ── Layer 2: source + package install (re-runs on source changes only) ───────
# README.md is required by hatchling to build the package (declared in pyproject.toml).
COPY README.md ./
COPY sealion_sidecar/ ./sealion_sidecar/

# --no-editable: install as a wheel into site-packages rather than editable
# mode. Editable installs create a .pth pointing back to /build which won't
# exist in the runtime image. hatchling force-include bakes schemas/ and
# prompts/ into the wheel so they resolve via PACKAGE_ROOT in _common.py.
RUN uv sync \
        --frozen \
        --no-dev \
        --no-editable

# ── Stage 2: runtime image ──────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

RUN groupadd --gid 1000 sealion \
 && useradd  --uid 1000 --gid sealion --no-create-home sealion

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# The default config path (~/.sealion/config.yaml) won't resolve for a
# no-home-dir user. Point explicitly at the docker-compose volume mount target.
ENV SEALION_CONFIG=/app/config.yaml

EXPOSE 8000

USER sealion

# stdio transport is intentionally excluded: it requires the MCP client to
# spawn this process as a subprocess and pipe stdin/stdout — impossible inside
# a container. Use streamable-http (or sse) for network-accessible deployment.
CMD ["sealion", "mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
