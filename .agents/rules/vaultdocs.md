---
trigger: always_on
---

Project Name:
VaultDocs

This is an enterprise-grade Secure Document Management System.

Architecture:
- Modular Monolith
- Clean Architecture
- SOLID Principles

Backend:
- Python 3.13
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x
- Alembic
- Pydantic v2

Development Standards:
- Ruff
- mypy
- pytest
- pre-commit
- Conventional Commits

Always follow these rules:

- Never create unnecessary files.
- Never generate placeholder code.
- Never use deprecated libraries.
- Always explain WHY before implementing.
- Keep modules loosely coupled and highly cohesive.
- Follow REST API best practices.
- Use dependency injection where appropriate.
- Always use type hints.
- Write production-ready code.
- Keep business logic out of API routes.
- Follow repository-service architecture.
- Never hardcode secrets.
- Always use environment variables.
- Generate clean documentation.
- Never skip error handling.
- Prefer async where appropriate.
- Every implementation should be scalable and testable.

Git Workflow:

main
develop
feature/*
bugfix/*
release/*
hotfix/*

Every feature must be developed in its own branch.

Never suggest direct commits to main.

Use Pull Requests.

Suggest Conventional Commit messages for every change.

Before writing code, explain:
1. Objective
2. Design
3. Files affected
4. Implementation approach
5. Commit message
