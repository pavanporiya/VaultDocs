"""
Main application entry point for VaultDocs.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from vaultdocs.api.router import router as api_router
from vaultdocs.core.logging_config import configure_logging, get_logger
from vaultdocs.core.settings import settings

# -------------------------------------------------------------------------
# Configure Logging
# -------------------------------------------------------------------------

configure_logging()

logger = get_logger(__name__)


# -------------------------------------------------------------------------
# Application Lifespan
# -------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """
    Handle application startup and shutdown events.
    """

    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    yield

    logger.info("Shutting down %s", settings.app_name)


# -------------------------------------------------------------------------
# FastAPI Application
# -------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)
app.include_router(api_router)

# -------------------------------------------------------------------------
# Root Endpoint
# -------------------------------------------------------------------------


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    Root endpoint.
    """

    return {
        "message": "Welcome to VaultDocs API",
    }
