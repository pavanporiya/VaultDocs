"""
Main application entry point for VaultDocs.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import text

from vaultdocs.api.router import router as api_router
from vaultdocs.core.logging_config import configure_logging, get_logger
from vaultdocs.core.settings import settings
from vaultdocs.db.session import engine

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
    Verifies database connectivity and database name before serving traffic.
    Never automatically initializes or resets an existing database.
    """
    logger.info(
        "Starting %s v%s (%s)",
        settings.app_name,
        settings.app_version,
        settings.app_environment,
    )

    # Startup Safety Guard: verify database connectivity and target database name
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database()"))
            active_db = result.scalar()
            expected_db = settings.postgres_db

            if active_db != expected_db:
                error_msg = (
                    f"STARTUP HALTED: Connected to database '{active_db}', expected "
                    f"'{expected_db}'. Check DATABASE_NAME / DATABASE_URL in configuration!"
                )
                logger.critical(error_msg)
                raise RuntimeError(error_msg)

            logger.info("Database connectivity verified: connected to '%s'", active_db)
    except Exception as exc:
        logger.critical("Database startup safety check failed: %s", exc)
        raise RuntimeError(f"Database startup safety check failed: {exc}") from exc

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
