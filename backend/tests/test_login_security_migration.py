"""
Migration safety tests for the device-approval login security tables.

Runs Alembic strictly against the isolated VaultDocs_test database
(hard-guarded here as well as in conftest) and proves that:

* the new revision upgrades a clean database to head,
* the new tables exist after upgrade,
* downgrading the new revision preserves pre-existing data (users),
* re-upgrading preserves that data again.

No destructive SQL is executed against any database other than the
isolated test database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.engine.url import make_url

from vaultdocs.core.settings import settings
from vaultdocs.db.base import Base

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_REVISION = "9c1f7a2b5e31"

TEST_DB_NAME = "VaultDocs_test"

LOGIN_SECURITY_TABLES = (
    "login_challenges",
    "trusted_devices",
)


def _alembic_url() -> str:
    """Sync Alembic URL pinned to the isolated test database, hard-guarded."""
    url = make_url(settings.alembic_database_url)
    resolved_db = url.database
    if resolved_db != TEST_DB_NAME:
        raise RuntimeError(
            f"CRITICAL SAFETY VIOLATION: migration test resolved database "
            f"'{resolved_db}'. Only '{TEST_DB_NAME}' is allowed!"
        )
    return url.render_as_string(hide_password=False)


def _alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


@pytest.fixture
def migrated_engine():
    """
    Fresh engine on VaultDocs_test with the schema brought to head.

    The schema is dropped first (test DB only) so the test starts from a
    clean slate, then upgraded through Alembic like a real deployment.
    """
    engine = sa.create_engine(_alembic_url())

    # Hard guard on the live wire before any DDL.
    with engine.connect() as conn:
        active_db = conn.execute(sa.text("SELECT current_database()")).scalar()
        if active_db != TEST_DB_NAME:
            engine.dispose()
            raise RuntimeError(
                f"CRITICAL SAFETY VIOLATION: connected to '{active_db}'. "
                f"Refusing migration DDL against non-test database!"
            )

    # Clean slate (metadata reflects ALL models incl. the new tables).
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))

    command.upgrade(_alembic_config(), "head")

    yield engine

    # Leave the test DB clean for subsequent fixtures (they create_all).
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))
    engine.dispose()


def test_upgrade_creates_login_security_tables(migrated_engine) -> None:
    inspector = sa.inspect(migrated_engine)
    tables = set(inspector.get_table_names())

    for table in LOGIN_SECURITY_TABLES:
        assert table in tables, f"Missing table after upgrade: {table}"

    assert "users" in tables

    # Unique index on the device credential hash (only hashes stored).
    device_indexes = {index["name"] for index in inspector.get_indexes("trusted_devices")}
    assert "ix_trusted_devices_device_token_hash" in device_indexes

    challenge_indexes = {index["name"] for index in inspector.get_indexes("login_challenges")}
    assert "ix_login_challenges_challenge_id" in challenge_indexes


def test_downgrade_preserves_existing_data(migrated_engine) -> None:
    """Pre-existing rows survive downgrade + re-upgrade of the new revision."""
    with migrated_engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO users (id, full_name, email, password_hash, "
                "is_active, is_superuser, is_verified, otp_failed_attempts, "
                "reset_token_failed_attempts, created_at, updated_at) "
                "VALUES (gen_random_uuid(), 'Migration Tester', "
                "'migration_t@example.com', 'hash', true, false, true, 0, 0, "
                "now(), now())"
            )
        )

    with migrated_engine.connect() as conn:
        count = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE email = 'migration_t@example.com'")
        ).scalar()
        assert count == 1

    # Drop only the new revision (its own tables); everything else stays.
    command.downgrade(_alembic_config(), "-1")

    with migrated_engine.connect() as conn:
        inspector = sa.inspect(migrated_engine)
        tables = set(inspector.get_table_names())
        for table in LOGIN_SECURITY_TABLES:
            assert table not in tables, f"Table {table} should be dropped"

        count = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE email = 'migration_t@example.com'")
        ).scalar()
        assert count == 1, "Downgrade must never touch pre-existing users"

    # Re-apply the new revision and confirm data is still intact.
    command.upgrade(_alembic_config(), "head")

    with migrated_engine.connect() as conn:
        inspector = sa.inspect(migrated_engine)
        tables = set(inspector.get_table_names())
        for table in LOGIN_SECURITY_TABLES:
            assert table in tables

        count = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE email = 'migration_t@example.com'")
        ).scalar()
        assert count == 1, "Re-upgrade must never touch pre-existing users"


def test_new_revision_is_head(migrated_engine) -> None:
    """The device-approval revision is applied as the single head."""
    from alembic.script import ScriptDirectory

    config = _alembic_config()
    script = ScriptDirectory.from_config(config)
    assert script.get_current_head() == NEW_REVISION
