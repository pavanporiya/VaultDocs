# VaultDocs — Deployment & Infrastructure Guide

> **Document ID:** DOC-007
> **Version:** 1.0.0
> **Status:** Approved
> **Author:** Pavan (Software Architect / Project Lead)
> **Contributors:** Raj (Backend Developer), Tirth (Backend Developer)
> **Created Date:** 2026-07-20
> **Last Updated:** 2026-07-20
> **Classification:** Internal Engineering Documentation

---

## Executive Summary

This Deployment & Infrastructure Guide outlines the operational environment architecture, Docker containerization strategy, Docker Compose orchestration, environment variable management, CI/CD pipeline automation, zero-downtime deployment rules, and observability monitoring for VaultDocs.

---

## Table of Contents

1. [Deployment Topology & Environments](#1-deployment-topology--environments)
2. [Containerization & Dockerfile Architecture](#2-containerization--dockerfile-architecture)
3. [Docker Compose Local & Staging Orchestration](#3-docker-compose-local--staging-orchestration)
4. [Environment Configuration Management](#4-environment-configuration-management)
5. [CI/CD Pipeline Architecture (GitHub Actions)](#5-cicd-pipeline-architecture-github-actions)
6. [Zero-Downtime Deployment & Database Migrations](#6-zero-downtime-deployment--database-migrations)
7. [Observability, Health Checks & Monitoring](#7-observability-health-checks--monitoring)
8. [Disaster Recovery & Rollback Strategy](#8-disaster-recovery--rollback-strategy)

---

## 1. Deployment Topology & Environments

VaultDocs supports three standard operational deployment environments:

```
+-----------------------------------------------------------------------------------+
|                            ENVIRONMENT DEPLOYMENT FLOW                            |
|                                                                                   |
|  +--------------------+      Git Push       +----------------------------------+  |
|  | Local / Dev        |  ===============>   | Staging Environment              |  |
|  | - Docker Compose   |                     | - Docker Compose / K8s           |  |
|  | - Local POSIX Storage|                    | - Staging Postgres & Redis       |  |
|  +--------------------+                     +-----------------+----------------+  |
|                                                               |                   |
|                                                Manual Approval|                   |
|                                                               v                   |
|                                             +----------------------------------+  |
|                                             | Production Environment           |  |
|                                             | - Load Balancer (SSL Termination)|  |
|                                             | - Horizontally Scaled Containers |  |
|                                             | - Managed Postgres (PITR Enabled)|  |
|                                             | - High Availability Redis Cluster|  |
|                                             +----------------------------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 2. Containerization & Dockerfile Architecture

VaultDocs utilizes multi-stage Docker builds to produce slim, secure, production-ready image artifacts:

```dockerfile
# Stage 1: Build & Dependency Resolution
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev

# Stage 2: Minimal Production Runtime
FROM python:3.13-slim AS runner

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd -g 999 vaultdocs && \
    useradd -r -u 999 -g vaultdocs vaultdocs && \
    mkdir -p /var/vaultdocs/data && \
    chown -R vaultdocs:vaultdocs /var/vaultdocs

COPY --from=builder /app/.venv /app/.venv
COPY backend /app/backend

USER vaultdocs

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 3. Docker Compose Local & Staging Orchestration

The system services are orchestrated locally and in staging using `docker-compose.yml`:

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - POSTGRES_SERVER=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=vaultdocs
      - POSTGRES_USER=vaultdocs_user
      - POSTGRES_PASSWORD=vaultdocs_pass
      - REDIS_URL=redis://redis:6379/0
      - STORAGE_VAULT_PATH=/var/vaultdocs/data
      - JWT_SECRET_KEY=dev_secret_change_in_production_32bytes!
    volumes:
      - vault_data:/var/vaultdocs/data
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:17-alpine
    environment:
      POSTGRES_DB: vaultdocs
      POSTGRES_USER: vaultdocs_user
      POSTGRES_PASSWORD: vaultdocs_pass
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vaultdocs_user -d vaultdocs"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.4-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pg_data:
  vault_data:
```

---

## 4. Environment Configuration Management

All configuration variables are declared in `.env` files and validated by Pydantic:

| Variable Name | Required | Default Value | Description |
| :--- | :---: | :---: | :--- |
| `ENVIRONMENT` | Yes | `development` | Deployment tier (`development`, `staging`, `production`). |
| `POSTGRES_SERVER` | Yes | `localhost` | PostgreSQL database host address. |
| `POSTGRES_PORT` | No | `5432` | Database TCP port. |
| `POSTGRES_DB` | Yes | `vaultdocs` | Primary database name. |
| `POSTGRES_USER` | Yes | — | Database user login. |
| `POSTGRES_PASSWORD` | Yes | — | Database authentication password (Secret). |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis cache & session store connection URL. |
| `STORAGE_VAULT_PATH`| Yes | `/var/vaultdocs/data` | Disk path for binary document storage vault. |
| `JWT_SECRET_KEY` | Yes | — | Cryptographic secret key for signing JWT tokens (Secret). |

---

## 5. CI/CD Pipeline Architecture (GitHub Actions)

VaultDocs utilizes GitHub Actions (`.github/workflows/ci.yml`) for automated integration and deployment:

```yaml
name: VaultDocs CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_DB: vaultdocs_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
      redis:
        image: redis:7.4-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
      - name: Install Dependencies
        run: uv sync --all-extras
      - name: Run Ruff Lint Check
        run: uv run ruff check .
      - name: Run mypy Type Check
        run: uv run mypy backend/app
      - name: Run Pytest Suite
        run: uv run pytest --cov=backend/app tests/
        env:
          POSTGRES_SERVER: localhost
          POSTGRES_PORT: 5432
          POSTGRES_DB: vaultdocs_test
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_password
          REDIS_URL: redis://localhost:6379/0
          JWT_SECRET_KEY: ci_secret_key_for_testing_purposes_only
```

---

## 6. Zero-Downtime Deployment & Database Migrations

To avoid service interruptions during updates:

1. **Expand-Contract Schema Migrations:** All database schema changes via Alembic must be backward compatible (add columns as nullable first; drop old columns in subsequent releases).
2. **Migration Execution Window:** Run `uv run alembic upgrade head` as a pre-deployment step prior to updating container images.
3. **Rolling Updates:** Replace web application instances incrementally behind a load balancer.

---

## 7. Observability, Health Checks & Monitoring

### 7.1 Liveness & Readiness Probes

FastAPI exposes system health status endpoints:

* `GET /health` — Liveness probe returning `200 OK {"status": "alive"}`.
* `GET /ready` — Readiness probe checking database and Redis connectivity.

### 7.2 Observability Stack

* **Metrics:** Prometheus endpoint metrics (`/metrics`).
* **Structured Logs:** Streamed JSON logs piped to stdout for collection by Vector / FluentBit / CloudWatch.

---

## 8. Disaster Recovery & Rollback Strategy

1. **Container Rollback:** In case of critical failure, redeploy previous tagged Docker image (`vaultdocs-app:v1.0.X`).
2. **Database Rollback:** If migration rollback is required, execute `uv run alembic downgrade -1`.
