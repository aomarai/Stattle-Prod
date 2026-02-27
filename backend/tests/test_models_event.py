"""
Tests for the Event SQLAlchemy model and related enums.

Covers:
- EventSource enum values.
- EventType enum values.
- Creating and persisting an Event.
- Nullable / required fields.
- Unique constraint on github_event_id.
- Foreign key to User.
"""

from datetime import datetime, timezone

import pytest
from app.models.event import Event, EventSource, EventType
from sqlalchemy.exc import IntegrityError
from tests.conftest import make_user


class TestEventSourceEnum:
    """Tests for the EventSource enum."""

    def test_github_value(self):
        """EventSource.GITHUB has the correct string value."""
        assert EventSource.GITHUB.value == "github"

    def test_gitlab_value(self):
        """EventSource.GITLAB has the correct string value."""
        assert EventSource.GITLAB.value == "gitlab"

    def test_bitbucket_value(self):
        """EventSource.BITBUCKET has the correct string value."""
        assert EventSource.BITBUCKET.value == "bitbucket"

    def test_all_members(self):
        """EventSource contains exactly the expected members."""
        assert set(EventSource) == {
            EventSource.GITHUB,
            EventSource.GITLAB,
            EventSource.BITBUCKET,
        }


class TestEventTypeEnum:
    """Tests for the EventType enum."""

    def test_commit_value(self):
        """EventType.COMMIT has the correct string value."""
        assert EventType.COMMIT.value == "commit"

    def test_pull_request_value(self):
        """EventType.PULL_REQUEST has the correct string value."""
        assert EventType.PULL_REQUEST.value == "pull_request"

    def test_issue_value(self):
        """EventType.ISSUE has the correct string value."""
        assert EventType.ISSUE.value == "issue"

    def test_comment_value(self):
        """EventType.COMMENT has the correct string value."""
        assert EventType.COMMENT.value == "comment"

    def test_all_members(self):
        """EventType contains exactly the expected members."""
        assert set(EventType) == {
            EventType.COMMIT,
            EventType.PULL_REQUEST,
            EventType.ISSUE,
            EventType.COMMENT,
        }


class TestEventCreation:
    """Tests for creating and persisting Event instances."""

    def _add_user(self, db_session) -> int:
        """Helper: persist a User and return its id."""
        user = make_user()
        db_session.add(user)
        db_session.flush()
        return user.id

    def test_create_event_all_fields(self, db_session):
        """Event can be created with all fields and persisted."""
        uid = self._add_user(db_session)
        occurred = datetime(2024, 3, 15, 12, 0, tzinfo=timezone.utc)
        ingested = datetime(2024, 3, 15, 12, 1, tzinfo=timezone.utc)

        event = Event(
            user_id=uid,
            source=EventSource.GITHUB,
            type=EventType.PULL_REQUEST,
            data={"action": "opened", "number": 42},
            occurred_at=occurred,
            ingested_at=ingested,
            github_event_id="gh-evt-001",
        )
        db_session.add(event)
        db_session.flush()

        assert event.id is not None
        assert event.user_id == uid
        assert event.source == EventSource.GITHUB
        assert event.type == EventType.PULL_REQUEST
        assert event.data == {"action": "opened", "number": 42}
        assert event.occurred_at == occurred
        assert event.ingested_at == ingested
        assert event.github_event_id == "gh-evt-001"

    def test_create_event_without_github_event_id(self, db_session):
        """Event can be created without github_event_id (nullable field)."""
        uid = self._add_user(db_session)

        event = Event(
            user_id=uid,
            source=EventSource.GITLAB,
            type=EventType.COMMIT,
            data={"sha": "abc123"},
            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            github_event_id=None,
        )
        db_session.add(event)
        db_session.flush()

        assert event.id is not None
        assert event.github_event_id is None

    def test_multiple_events_null_github_event_id(self, db_session):
        """Multiple events may have github_event_id=None (null is not unique-constrained)."""
        uid = self._add_user(db_session)

        e1 = Event(
            user_id=uid,
            source=EventSource.GITHUB,
            type=EventType.ISSUE,
            data={},
            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            github_event_id=None,
        )
        e2 = Event(
            user_id=uid,
            source=EventSource.GITHUB,
            type=EventType.COMMENT,
            data={},
            occurred_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            ingested_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            github_event_id=None,
        )
        db_session.add_all([e1, e2])
        db_session.flush()  # Should not raise

        assert e1.id is not None
        assert e2.id is not None

    def test_duplicate_github_event_id_raises(self, db_session):
        """Two events with the same github_event_id raises IntegrityError."""
        uid = self._add_user(db_session)

        e1 = Event(
            user_id=uid,
            source=EventSource.GITHUB,
            type=EventType.COMMIT,
            data={},
            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            ingested_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            github_event_id="duplicate-id",
        )
        e2 = Event(
            user_id=uid,
            source=EventSource.GITHUB,
            type=EventType.COMMIT,
            data={},
            occurred_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            ingested_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            github_event_id="duplicate-id",
        )
        db_session.add_all([e1, e2])
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_all_event_sources_persist(self, db_session):
        """Events with each EventSource value can be persisted."""
        uid = self._add_user(db_session)

        for i, source in enumerate(EventSource):
            event = Event(
                user_id=uid,
                source=source,
                type=EventType.COMMIT,
                data={},
                occurred_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
                ingested_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            )
            db_session.add(event)

        db_session.flush()  # Should not raise

    def test_all_event_types_persist(self, db_session):
        """Events with each EventType value can be persisted."""
        uid = self._add_user(db_session)

        for i, event_type in enumerate(EventType):
            event = Event(
                user_id=uid,
                source=EventSource.GITHUB,
                type=event_type,
                data={},
                occurred_at=datetime(2024, 2, i + 1, tzinfo=timezone.utc),
                ingested_at=datetime(2024, 2, i + 1, tzinfo=timezone.utc),
            )
            db_session.add(event)

        db_session.flush()  # Should not raise
