# VaultDocs — Secure Document Management System

> Enterprise-grade document management platform built with Clean Architecture principles.

## Overview

DocFlow is a secure, scalable document management system designed for organizations that need
reliable document storage, retrieval, versioning, and access control.

## Tech Stack

| Layer          | Technology                        |
|----------------|-----------------------------------|
| Language       | Python 3.13                       |
| Framework      | FastAPI                           |
| Database       | PostgreSQL                        |
| ORM            | SQLAlchemy 2.x                    |
| Migrations     | Alembic                           |
| Validation     | Pydantic v2                       |
| Package Mgr    | uv                                |
| Containerization | Docker / Docker Compose         |
| CI/CD          | GitHub Actions                    |
| Testing        | pytest                            |
| Linting        | Ruff                              |
| Type Checking  | mypy                              |

## Architecture

This project follows a **Modular Monolith** architecture with **Clean Architecture** layers:

```
Presentation (API)  →  Application (Use Cases)  →  Domain (Business Rules)  →  Infrastructure (DB, Storage)
```

See [docs/Architecture.md](docs/Architecture.md) for full details.

## Getting Started

> **Prerequisites:** Python 3.13+, Docker, Docker Compose, uv

```bash
# Clone the repository
git clone https://github.com/<org>/VaultDocs.git
cd VaultDocs

# Copy environment variables
cp .env.example .env

# Install dependencies
uv sync

# Start services
docker compose up -d

# Run migrations
alembic upgrade head

# Start the development server
uv run uvicorn backend.src.VaultDocs.main:app --reload
```

## Project Structure

```
VaultDocs/
├── backend/              # Backend application (Python / FastAPI)
│   ├── src/VaultDocs/      # Source code organized by Clean Architecture
│   ├── tests/            # Unit, integration, and e2e tests
│   ├── scripts/          # Backend utility scripts
│   └── alembic/          # Database migration configuration
├── frontend/             # Frontend application (future)
├── docs/                 # Project documentation
├── deployment/           # Deployment configurations
├── .github/              # GitHub Actions, issue & PR templates
└── scripts/              # Repository-level utility scripts
```

## Team

| Role           | Responsibility                             |
|----------------|--------------------------------------------|
| Team Lead      | Architecture, code review, sprint planning |
| Developer 1    | Backend modules, API endpoints             |
| Developer 2    | Infrastructure, testing, DevOps            |

## Documentation

- [Architecture](docs/Architecture.md)
- [API Design](docs/API_Design.md)
- [Database Design](docs/Database_Design.md)
- [Git Workflow](docs/Git_Workflow.md)
- [Branching Strategy](docs/Branching_Strategy.md)
- [Coding Standards](docs/Coding_Standards.md)
- [Sprint Planning](docs/Sprint_Planning.md)
- [Deployment Guide](docs/Deployment_Guide.md)
- [Requirements](docs/Requirements.md)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
