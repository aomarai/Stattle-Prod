"""
Shared pytest fixtures for database model tests.

Uses SQLite in-memory database to avoid needing a live Postgres instance
for unit tests, while still exercising all SQLAlchemy ORM behaviour.

JSONB columns are overridden with SQLAlchemy's JSON type so that SQLite
can render them correctly during schema creation.
"""

from datetime import datetime, timezone

import pytest
from app.models import Base
from app.models.event import Event, EventSource, EventType
from app.models.metrics import DailyStats, PRAnalytics, PRState, WeeklyLanguages
from app.models.user import User
from sqlalchemy import create_engine, event as sa_event, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import sessionmaker, Session


def _override_jsonb_for_sqlite(metadata):
    """
    Replace all JSONB column types with JSON so the schema can be created
    on a SQLite database (used for testing).

    This mutates the metadata in-place and should only be called in test
    setup before Base.metadata.create_all().
    """
    for table in metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, JSONB):
                column.type = JSON()


@pytest.fixture(scope="session")
def engine():
    """
    Create an in-memory SQLite engine for the test session.

    JSONB columns are swapped for JSON before schema creation so that
    SQLite can render them.
    """
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @sa_event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _):
        """Enable foreign key enforcement in SQLite."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _override_jsonb_for_sqlite(Base.metadata)
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    """
    Provide a transactional database session that is rolled back after each test.

    This keeps tests isolated without recreating the schema on every run.
    """
    connection = engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Reusable model factory helpers
# ---------------------------------------------------------------------------


def make_user(
    authentik_sub: str = "sub-123",
    email: str = "test@example.com",
    username: str = "testuser",
    github_username: str = "gh-testuser",
) -> User:
    """Return a new, unsaved User instance with sensible defaults."""
    return User(
        authentik_sub=authentik_sub,
        email=email,
        username=username,
        github_username=github_username,
    )


def make_daily_stats(user_id: int, date: datetime = None) -> DailyStats:
    """Return a new, unsaved DailyStats instance."""
    return DailyStats(
        user_id=user_id,
        date=date or datetime(2024, 1, 1, tzinfo=timezone.utc),
        commit_count=5,
        pr_opened_count=2,
        pr_merged_count=1,
        pr_reviewed_count=3,
        issues_opened_count=4,
        lines_added_count=100,
        lines_deleted_count=50,
        repos_contributed_to_count=2,
    )


def make_pr_analytics(user_id: int, github_pr_id: int = 1) -> PRAnalytics:
    """Return a new, unsaved PRAnalytics instance."""
    return PRAnalytics(
        user_id=user_id,
        github_pr_id=github_pr_id,
        repo_name="org/repo",
        number=42,
        title="Add feature X",
        state=PRState.OPEN,
        opened_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        review_count=2,
        comment_count=5,
        files_changed=3,
        lines_added=80,
        lines_deleted=20,
    )


def make_weekly_languages(user_id: int) -> WeeklyLanguages:
    """Return a new, unsaved WeeklyLanguages instance."""
    return WeeklyLanguages(
        user_id=user_id,
        language="Python",
        week_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        lines_written=500,
        repo_count=3,
    )
