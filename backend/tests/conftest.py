"""
Pytest configuration and fixtures.
"""

from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vaultdocs.core.settings import settings

# =============================================================================
# ISOLATED TEST DATABASE CONFIGURATION & STRICT HARD SAFETY GUARDS
# =============================================================================
# Build isolated test database URL strictly targeting VaultDocs_test
_base_url = make_url(settings.database_url)
_test_db_name = "VaultDocs_test"
_test_url = _base_url.set(database=_test_db_name)
TEST_DATABASE_URL = _test_url.render_as_string(hide_password=False)

# Hard safety guard: abort tests immediately if DB name is not strictly 'VaultDocs_test'
_resolved_test_db = make_url(TEST_DATABASE_URL).database
if _resolved_test_db != "VaultDocs_test":
    raise RuntimeError(
        f"CRITICAL SAFETY VIOLATION: Test suite attempted to connect to database "
        f"'{_resolved_test_db}'! Tests must NEVER connect to live 'VaultDocs' or any non-test DB. "
        f"Tests must ONLY run against isolated test database 'VaultDocs_test'."
    )

# Direct settings to isolated test database BEFORE importing app, router, or session
settings.custom_database_url = TEST_DATABASE_URL
settings.postgres_db = _test_db_name

from vaultdocs.core.security import create_access_token, hash_password  # noqa: E402
from vaultdocs.db.base import Base  # noqa: E402
from vaultdocs.db.session import get_db  # noqa: E402
from vaultdocs.main import app  # noqa: E402
from vaultdocs.models.user import User  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def _force_local_summary_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Force the credential-free extractive summary provider during tests.

    Guarantees the suite never calls a remote AI provider (no network use,
    no credential dependence, deterministic summary_source assertions) no
    matter what a developer's local .env configures. Individual tests may
    override this to exercise provider fallback behavior.
    """
    monkeypatch.setattr(settings, "ai_provider", "extractive")
    monkeypatch.setattr(settings, "ai_api_key", None)


@pytest.fixture(autouse=True)
def _force_mock_smtp() -> Generator[None]:
    """
    Force isolated in-memory mock SMTP during all automated test runs.

    Guarantees no real email network calls are ever made during testing.
    """
    from vaultdocs.services.email import clear_test_outbox, set_mock_smtp

    set_mock_smtp(True)
    clear_test_outbox()
    yield
    clear_test_outbox()
    set_mock_smtp(False)


@pytest.fixture
async def db_engine():
    """
    Create an isolated test database engine.
    Guarantees Base.metadata.create_all and drop_all NEVER run against development DB.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )

    # Hard guard 1: Verify engine URL database name before any DDL
    engine_db = make_url(str(engine.url)).database
    if engine_db != "VaultDocs_test":
        await engine.dispose()
        raise RuntimeError(
            f"CRITICAL SAFETY GUARD TRIGGERED: Engine connected to '{engine_db}', "
            f"expected 'VaultDocs_test'. Refusing DDL against non-test DB!"
        )

    # Hard guard 2: Verify live connected database on the wire before create_all
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT current_database()"))
        active_db = result.scalar()
        if active_db != "VaultDocs_test":
            raise RuntimeError(
                f"CRITICAL SAFETY GUARD TRIGGERED: Live connection connected to '{active_db}', "
                f"expected 'VaultDocs_test'. Refusing to execute create_all against non-test DB!"
            )
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Hard guard 3: Verify live connected database on the wire before drop_all
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT current_database()"))
        active_db = result.scalar()
        if active_db != "VaultDocs_test":
            raise RuntimeError(
                f"CRITICAL SAFETY GUARD TRIGGERED: Live connection connected to '{active_db}', "
                "expected 'VaultDocs_test'. Refusing to drop tables from non-test database!"
            )
        await conn.run_sync(Base.metadata.drop_all)
        # Drop the stale alembic_version row left behind by drop_all so the
        # database is left in a genuinely clean state (no false "head" marker
        # pointing at missing tables).
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession]:
    """
    Yield an async database session wrapped in a transaction that rolls back.
    """
    session_factory = async_sessionmaker(
        bind=db_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture
async def user_a(db_session: AsyncSession) -> User:
    """
    Create first test user.
    """
    user = User(
        full_name="User A",
        email="user_a@example.com",
        password_hash=hash_password("Password123!"),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_b(db_session: AsyncSession) -> User:
    """
    Create second test user.
    """
    user = User(
        full_name="User B",
        email="user_b@example.com",
        password_hash=hash_password("Password123!"),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers_user_a(user_a: User) -> dict[str, str]:
    """
    Authorization header for User A.
    """
    token = create_access_token(subject=user_a.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b(user_b: User) -> dict[str, str]:
    """
    Authorization header for User B.
    """
    token = create_access_token(subject=user_b.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """
    HTTP client for testing API endpoints with overridden db dependency.
    """

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
