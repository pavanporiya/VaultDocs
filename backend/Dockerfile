# =============================================================================
# VaultDocs — Backend Dockerfile
# =============================================================================
# Multi-stage build for a minimal, secure production image.
#
# Stage 1 (builder): Install dependencies using uv
# Stage 2 (runtime): Copy only what's needed to run the app
#
# Build:  docker build -t vaultdocs-backend ./backend
# Run:    docker run -p 8000:8000 vaultdocs-backend
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Builder
# ---------------------------------------------------------------------------
# WHY python:3.13-slim?
#   - "slim" variant excludes build tools we don't need at runtime (gcc, etc.)
#   - Debian-based, so system packages are easy to install if needed
#   - ~150MB base vs ~900MB for the full image
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS builder

# WHY set these environment variables?
#   PYTHONDONTWRITEBYTECODE=1 — Prevents .pyc files (smaller image, no stale cache)
#   PYTHONUNBUFFERED=1 — Ensures print/log output is sent immediately to stdout
#   (critical for Docker log collection)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# WHY install uv in the builder?
#   uv resolves and installs dependencies 10-100x faster than pip.
#   We use the official installer script from Astral.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# WHY set a WORKDIR?
#   All subsequent commands (COPY, RUN) execute relative to this directory.
#   /app is a common convention for application code in containers.
WORKDIR /app

# WHY copy dependency files FIRST (before source code)?
#   Docker layer caching: if pyproject.toml and uv.lock haven't changed,
#   Docker reuses the cached dependency layer and skips re-installation.
#   This is a HUGE time saver — dependencies change rarely, code changes often.
COPY pyproject.toml uv.lock ./

# WHY use --no-install-project?
#   We only want to install dependencies, not the project itself.
#   The project source will be copied in the runtime stage.
# WHY use --frozen?
#   Ensures exact versions from uv.lock are installed (no resolution).
#   Guarantees reproducible builds.
# WHY use --no-dev?
#   Production images don't need test tools, linters, or dev utilities.
#   Smaller image, fewer attack vectors.
RUN uv sync --frozen --no-install-project --no-dev

# ---------------------------------------------------------------------------
# Stage 2: Runtime
# ---------------------------------------------------------------------------
# WHY a second stage?
#   The builder stage may have cached downloads, build artifacts, and
#   intermediate files. This fresh stage starts clean and copies only
#   the final virtual environment and source code.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

# Same environment variables as builder (needed at runtime too)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# WHY create a non-root user?
#   Security best practice: if the application is compromised, the attacker
#   has limited permissions. Never run production containers as root.
RUN groupadd --gid 1000 vaultdocs \
    && useradd --uid 1000 --gid vaultdocs --create-home vaultdocs

WORKDIR /app

# WHY copy the virtual environment from the builder?
#   This brings in all installed dependencies without the build tools,
#   cache files, or intermediate artifacts from the builder stage.
COPY --from=builder /app/.venv /app/.venv

# WHY copy backend source code?
#   This is the actual application code that runs in the container.
COPY backend/src/ ./backend/src/

# WHY copy alembic separately?
#   Alembic migrations need to be available for database schema management.
COPY backend/alembic/ ./backend/alembic/

# WHY update PATH?
#   Adding .venv/bin to PATH means we can run `python`, `uvicorn`, `alembic`
#   directly without activating the virtual environment.
ENV PATH="/app/.venv/bin:$PATH"

# WHY switch to non-root user?
#   All subsequent commands (and the running container) execute as "vaultdocs"
#   user, not root. This is a security hardening measure.
USER vaultdocs

# WHY EXPOSE 8000?
#   Documents which port the application listens on.
#   This is informational only — it doesn't actually publish the port.
#   The port mapping happens in docker-compose.yml or `docker run -p`.
EXPOSE 8000

# WHY use this CMD?
#   uvicorn is the ASGI server that runs our FastAPI application.
#   --host 0.0.0.0 — Listen on all interfaces (required inside containers)
#   --port 8000 — Match the EXPOSE directive
#   NOTE: This command will be overridden in docker-compose.yml for
#   development (adding --reload for hot-reloading).
CMD ["uvicorn", "vaultdocs.main:app", "--host", "0.0.0.0", "--port", "8000"]
