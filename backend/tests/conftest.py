"""
Pytest configuration and fixtures.
"""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from vaultdocs.core.security import create_access_token, hash_password
from vaultdocs.core.settings import settings
from vaultdocs.db.base import Base
from vaultdocs.db.session import get_db
from vaultdocs.main import app
from vaultdocs.models.user import User


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine():
    """
    Create a test database engine.
    """
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
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
