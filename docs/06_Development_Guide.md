# VaultDocs — Development Guide & Standards

> **Document ID:** DOC-006
> **Version:** 1.0.0
> **Status:** Approved
> **Author:** Pavan (Software Architect / Project Lead)
> **Contributors:** Raj (Backend Developer), Tirth (Backend Developer)
> **Created Date:** 2026-07-20
> **Last Updated:** 2026-07-20
> **Classification:** Internal Engineering Documentation

---

## Executive Summary

This Development Guide establishes engineering standards, directory organization, Git branching strategies, code formatting rules, static analysis protocols, and testing practices for the VaultDocs platform. Adherence to this guide ensures team consistency, zero code duplication, high test coverage, and smooth pull request reviews.

---

## Table of Contents

1. [Repository & Project Structure](#1-repository--project-structure)
2. [Development Environment Setup](#2-development-environment-setup)
3. [Git Workflow & Branching Strategy](#3-git-workflow--branching-strategy)
4. [Conventional Commit Standard](#4-conventional-commit-standard)
5. [Code Quality & Static Analysis](#5-code-quality--static-analysis)
6. [Testing Strategy & Execution](#6-testing-strategy--execution)
7. [Pull Request (PR) & Code Review Guidelines](#7-pull-request-pr--code-review-guidelines)

---

## 1. Repository & Project Structure

VaultDocs uses a clean repository layout separating application modules, infrastructure configs, and tests:

```
DOCFLOW-PROJECT/
├── .agents/                    # Agentic & workspace configurations
├── .github/                    # GitHub Actions CI/CD workflows
│   └── workflows/
│       └── ci.yml
├── backend/                    # Python Backend Source Root
│   ├── app/
│   │   ├── api/                # Presentation Layer (FastAPI Routes)
│   │   │   └── v1/
│   │   ├── core/               # Application & Domain Shared Core
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── exceptions.py
│   │   ├── modules/            # Clean Architecture Modules
│   │   │   ├── auth/
│   │   │   ├── documents/
│   │   │   ├── versions/
│   │   │   ├── search/
│   │   │   └── audit/
│   │   └── main.py             # ASGI Application Entrypoint
│   ├── tests/                  # Pytest Automated Test Suite
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── Dockerfile
│   └── pyproject.toml          # Tooling & Dependency Configuration
├── deployment/                 # Deployment scripts and NGINX configs
├── docs/                       # Official Engineering Documentation
├── docker-compose.yml          # Local Dev Service Orchestration
├── pyproject.toml              # Workspace Root Package Configuration
├── README.md
└── uv.lock                     # Lockfile for Deterministic Installs
```

---

## 2. Development Environment Setup

VaultDocs leverages **`uv`** for Python package resolution and virtual environment management:

```bash
# 1. Clone the repository
git clone git@github.com:pavanporiya/VaultDocs.git
cd VaultDocs

# 2. Sync virtual environment and dependencies using uv
uv sync --all-extras

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Start PostgreSQL and Redis background services
docker compose up -d postgres redis

# 5. Run database migrations
uv run alembic upgrade head

# 6. Start the local FastAPI development server
uv run uvicorn backend.app.main:app --reload --port 8000
```

---

## 3. Git Workflow & Branching Strategy

VaultDocs enforces a strict GitFlow-inspired branching model:

```
main       =========================================> [Production Releases]
              \                              /
release/*      \                      ======/
                \                    /
develop    =========================================> [Integration]
              \             /    \          /
feature/*      \===========/      \========/          [Feature Work]
```

### Branch Types & Naming Standards

1. `main`: Production-ready branch. Protected. Only merges from `release/*` or `hotfix/*`.
2. `develop`: Active integration branch. Protected. All feature branches branch off and merge back here.
3. `feature/ISSUE-ID-short-name`: New feature development (e.g., `feature/VD-102-audit-logger`).
4. `bugfix/ISSUE-ID-short-name`: Non-urgent bug fixes (e.g., `bugfix/VD-204-jwt-clock-skew`).
5. `hotfix/ISSUE-ID-short-name`: Urgent production patches branching directly off `main`.

---

## 4. Conventional Commit Standard

All commit messages MUST follow the **Conventional Commits** specification:

```
<type>(<scope>): <short summary>

[optional body]
```

### Commit Types

* `feat`: A new feature implementation.
* `fix`: A bug fix.
* `docs`: Documentation updates only.
* `style`: Code formatting (formatting, missing semi-colons, no logic change).
* `refactor`: Code restructuring without bug fixes or new features.
* `test`: Adding or updating test cases.
* `chore`: Build process, tooling, or dependency updates.

### Examples

```bash
git commit -m "feat(auth): implement refresh token rotation in Redis"
git commit -m "fix(document): prevent memory leak during large file streaming"
git commit -m "docs: update 06_Development_Guide.md with Git branch rules"
```

---

## 5. Code Quality & Static Analysis

VaultDocs maintains strict automated quality checks:

### 5.1 Python Code Style & Formatting (`Ruff`)

* **PEP 8 Compliance:** Enforced via `Ruff`.
* **Line Length:** Maximum 99 characters.
* **Import Sorting:** Standard stdlib $\rightarrow$ Third-party $\rightarrow$ Local imports (`isort` rules via Ruff).

```bash
# Run Ruff linting
uv run ruff check .

# Run Ruff formatting
uv run ruff format .
```

### 5.2 Strict Static Type Checking (`mypy`)

* **Mode:** `--strict` enabled.
* **Requirements:** All function parameters and return types MUST have explicit type annotations.

```bash
# Run mypy strict type check
uv run mypy backend/app
```

---

## 6. Testing Strategy & Execution

VaultDocs mandates a minimum **85% code coverage** enforced via `pytest`:

```
+-----------------------------------------------------------------------------------+
|                                 TESTING TOPOLOGY                                  |
|                                                                                   |
|  +--------------------+   +---------------------------+   +--------------------+  |
|  | Unit Tests         |   | Integration Tests         |   | End-to-End Tests   |  |
|  | - Domain Entities  |   | - FastAPI API Routes      |   | - Full Ingestion   |  |
|  | - Value Objects    |   | - Async SQLAlchemy Repos  |   | - Token Lifecycle  |  |
|  | - Service Logic    |   | - Redis Cache Engine      |   | - Audit Trail      |  |
|  +--------------------+   +---------------------------+   +--------------------+  |
+-----------------------------------------------------------------------------------+
```

### Running Test Suite

```bash
# Run all unit and integration tests with coverage report
uv run pytest --cov=backend/app --cov-report=term-missing tests/
```

---

## 7. Pull Request (PR) & Code Review Guidelines

1. **Self-Review Checklist:** Before submitting a PR, verify:
   - `uv run ruff check .` passes without errors.
   - `uv run mypy backend/app` passes with zero type warnings.
   - `uv run pytest` passes 100% of test cases.
2. **Review Requirements:** At least **one approval** from a Project Lead or Senior Architect is required before merging into `develop`.
3. **Merge Strategy:** Use **Squash and Merge** to maintain a clean linear commit history.
