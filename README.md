# VaultDocs — Secure Document Management System

> Document management backend with authentication, nested folders, versioned files,
> search, and read-only document sharing.

## Overview

VaultDocs is a FastAPI backend for storing, versioning, searching, and sharing
documents. Users own folders and documents, upload/replace files with automatic
version history, and can grant other registered users read-only access to
individual documents.

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Language       | Python 3.13                       |
| Framework      | FastAPI                           |
| Database       | PostgreSQL 16                     |
| ORM            | SQLAlchemy 2.x (async)            |
| Migrations     | Alembic                           |
| Validation     | Pydantic v2                       |
| Package Mgr    | uv                                |
| Frontend       | React 19 + Vite (JavaScript)      |
| Containerization | Docker / Docker Compose         |
| CI/CD          | GitHub Actions                    |
| Testing        | pytest                            |
| Linting        | Ruff                              |
| Type Checking  | mypy (strict)                     |

## Quick Start

> **Prerequisites:** Python 3.13+, Node.js 18+, [uv](https://docs.astral.sh/uv/), Docker

```bash
# Clone + configure (once)
git clone https://github.com/pavanporiya/VaultDocs.git
cd VaultDocs
cp .env.example .env
```

### 1. Environment setup — Docker

```bash
docker compose up -d
```

Starts PostgreSQL and the backend. Database only: `docker compose up -d db`.

### 2. Backend

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn vaultdocs.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/v1/health
- Browser demo UI (register/login/upload/download/share): http://localhost:8000/demo

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- App: http://localhost:3000 (Vite proxies `/v1` requests to the backend automatically)

## Quality Checks

```bash
# Backend
uv run ruff check .
uv run ruff format --check .
uv run mypy backend/src
uv run pytest
uv run alembic check

# Frontend
cd frontend
npm run lint
npm run build
```

## Testing

```bash
uv run pytest
```

Tests run against the database configured in `.env` (default `localhost:5433`).
Each test creates its schema from the models and tears it down afterwards.

## Project Structure

```
VaultDocs/
├── backend/
│   ├── src/vaultdocs/        # Application source code
│   │   ├── api/              # FastAPI routers (v1) and dependencies
│   │   ├── core/             # Settings, security (JWT/hashing), logging
│   │   ├── db/               # Engine, session, base, mixins
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # Business logic
│   │   └── demo.html         # Browser demo page (served at /demo)
│   └── tests/                # pytest integration tests
├── alembic/                  # Alembic migrations (upgrade head from repo root)
├── docs/                     # Project documentation
├── frontend/                 # React + Vite frontend (`npm run dev`)
├── scripts/                  # Live E2E verification harnesses
├── .github/                  # GitHub Actions workflows
├── docker-compose.yml        # App + PostgreSQL for local development
├── backend/Dockerfile        # Backend image (multi-stage, non-root)
└── pyproject.toml            # Dependencies + tool configuration
```

## API Summary

| Area         | Endpoints |
|--------------|-----------|
| Auth         | `POST /v1/auth/register`, `POST /v1/auth/login`, `GET /v1/auth/me` |
| Folders      | CRUD under `/v1/folders` (nested via `parent_id`) |
| Documents    | CRUD under `/v1/documents`, search at `/v1/documents/search` |
| Files        | `POST/PUT /v1/documents/{id}/upload`, `GET /v1/documents/{id}/download` |
| Versions     | `GET /v1/documents/{id}/versions[/{version_id}[/download]]` |
| Sharing      | `POST/GET /v1/documents/{id}/shares`, `DELETE /v1/documents/{id}/shares/{share_id}` |

Sharing is read-only: recipients can view and download a shared document and its
versions but can never modify it or manage its shares. Owner-only management uses
safe 404 responses to avoid resource enumeration.

## Documentation

- [Project Overview](docs/01_Project_Overview.md)
- [Requirements Specification](docs/02_Software_Requirements_Specification.md)
- [System Architecture](docs/03_System_Architecture.md)
- [Database Design](docs/04_Database_Design.md)
- [API Design](docs/05_API_Design.md)
- [Development Guide](docs/06_Development_Guide.md)
- [Deployment Guide](docs/07_Deployment_Guide.md)
- [Product Roadmap](docs/08_Product_Roadmap.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
