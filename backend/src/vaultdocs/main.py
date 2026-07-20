"""VaultDocs FastAPI application foundation.

This module initializes the core FastAPI application for VaultDocs,
configuring application metadata, documentation endpoints (Swagger UI & ReDoc),
and application lifecycle management.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

# Configure logger for core application initialization
logger = logging.getLogger("vaultdocs")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Core Metadata Definitions
APP_TITLE: str = "VaultDocs API"
APP_DESCRIPTION: str = "Backend API for VaultDocs Secure Document Management System"
APP_VERSION: str = "0.1.0"

# Placeholder for OpenAPI tags metadata to organize future route specifications
TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "system",
        "description": "System operational and health status endpoints.",
    },
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle events (startup and shutdown).

    Provides an async context manager handling startup setup and shutdown cleanup.

    Args:
        _app: The initialized FastAPI application instance.

    Yields:
        None: Yields control back to the application execution context.
    """
    logger.info("Starting up VaultDocs API v%s...", APP_VERSION)
    yield
    logger.info("Shutting down VaultDocs API...")


app: FastAPI = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
