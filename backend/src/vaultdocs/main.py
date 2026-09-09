"""
Main application entry point for VaultDocs.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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


# -------------------------------------------------------------------------
# Browser Demo UI
# -------------------------------------------------------------------------


@app.get("/demo", include_in_schema=False)
async def demo() -> HTMLResponse:
    """
    Serve a lightweight browser demo for the API (register, login, upload,
    download, share, versions). Dev convenience only.
    """

    html = resources.files("vaultdocs").joinpath("demo.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)
