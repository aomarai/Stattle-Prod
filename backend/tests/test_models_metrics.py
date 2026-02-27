"""
Tests for the metrics SQLAlchemy models and PRState enum.

Covers:
- PRState enum values.
- DailyStats: creation, unique constraint (user_id + date).
- PRAnalytics: creation, all states, cycle_time property, __repr__.
- WeeklyLanguages: creation, unique constraint (user_id + language + week_start).
"""

from datetime import datetime, timezone

import pytest
from app.models.metrics import DailyStats, PRAnalytics, PRState, WeeklyLanguages
from sqlalchemy.exc import IntegrityError
from tests.conftest import (
    make_user,
    make_daily_stats,
    make_pr_analytics,
    make_weekly_languages,
)


class TestPRStateEnum:
    """Tests for the PRState enum."""

    def test_draft_value(self):
        """PRState.DRAFT has the correct string value."""
        assert PRState.DRAFT.value == "draft"

    def test_open_value(self):
        """PRState.OPEN has the correct string value."""
        assert PRState.OPEN.value == "open"

    def test_closed_value(self):
        """PRState.CLOSED has the correct string value."""
        assert PRState.CLOSED.value == "closed"

    def test_merged_value(self):
        """PRState.MERGED has the correct string value."""
        assert PRState.MERGED.value == "merged"

    def test_all_members(self):
        """PRState contains exactly the expected members."""
        assert set(PRState) == {
            PRState.DRAFT,
            PRState.OPEN,
            PRState.CLOSED,
            PRState.MERGED,
        }


class TestDailyStats:
    """Tests for the DailyStats model."""

    def _add_user(self, db_session) -> int:
        user = make_user()
        db_session.add(user)
        db_session.flush()
        return user.id

    def test_create_daily_stats(self, db_session):
        """DailyStats can be created and persisted with all fields."""
        uid = self._add_user(db_session)
        date = datetime(2024, 1, 15, tzinfo=timezone.utc)

        stats = DailyStats(
            user_id=uid,
            date=date,
            commit_count=10,
            pr_opened_count=3,
            pr_merged_count=2,
            pr_reviewed_count=4,
            issues_opened_count=1,
            lines_added_count=200,
            lines_deleted_count=75,
            repos_contributed_to_count=3,
        )
        db_session.add(stats)
        db_session.flush()

        assert stats.id is not None
        assert stats.user_id == uid
        assert stats.date == date
        assert stats.commit_count == 10
        assert stats.pr_opened_count == 3
        assert stats.pr_merged_count == 2
        assert stats.pr_reviewed_count == 4
        assert stats.issues_opened_count == 1
        assert stats.lines_added_count == 200
        assert stats.lines_deleted_count == 75
        assert stats.repos_contributed_to_count == 3

    def test_daily_stats_unique_user_date(self, db_session):
        """Inserting two DailyStats rows with same user_id and date raises IntegrityError."""
        uid = self._add_user(db_session)
        date = datetime(2024, 2, 1, tzinfo=timezone.utc)

        db_session.add(make_daily_stats(uid, date))
        db_session.flush()

        db_session.add(make_daily_stats(uid, date))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_daily_stats_different_dates_allowed(self, db_session):
        """Same user can have DailyStats for different dates."""
        uid = self._add_user(db_session)

        db_session.add(make_daily_stats(uid, datetime(2024, 3, 1, tzinfo=timezone.utc)))
        db_session.add(make_daily_stats(uid, datetime(2024, 3, 2, tzinfo=timezone.utc)))
        db_session.flush()  # Should not raise

    def test_daily_stats_different_users_same_date_allowed(self, db_session):
        """Different users can have DailyStats for the same date."""
        u1 = make_user(
            authentik_sub="sub-ds1", email="ds1@example.com", github_username="gh-ds1"
        )
        u2 = make_user(
            authentik_sub="sub-ds2", email="ds2@example.com", github_username="gh-ds2"
        )
        db_session.add_all([u1, u2])
        db_session.flush()

        date = datetime(2024, 4, 1, tzinfo=timezone.utc)
        db_session.add(make_daily_stats(u1.id, date))
        db_session.add(make_daily_stats(u2.id, date))
        db_session.flush()  # Should not raise

    def test_daily_stats_zero_counts(self, db_session):
        """DailyStats can be created with all-zero counts (valid inactive day)."""
        uid = self._add_user(db_session)
        stats = DailyStats(
            user_id=uid,
            date=datetime(2024, 5, 1, tzinfo=timezone.utc),
            commit_count=0,
            pr_opened_count=0,
            pr_merged_count=0,
            pr_reviewed_count=0,
            issues_opened_count=0,
            lines_added_count=0,
            lines_deleted_count=0,
            repos_contributed_to_count=0,
        )
        db_session.add(stats)
        db_session.flush()
        assert stats.id is not None


class TestPRAnalytics:
    """Tests for the PRAnalytics model and cycle_time property."""

    def _add_user(self, db_session) -> int:
        user = make_user()
        db_session.add(user)
        db_session.flush()
        return user.id

    def test_create_pr_analytics_open(self, db_session):
        """PRAnalytics can be created with state=OPEN and no closed/merged timestamps."""
        uid = self._add_user(db_session)
        pr = make_pr_analytics(uid, github_pr_id=100)
        db_session.add(pr)
        db_session.flush()

        assert pr.id is not None
        assert pr.state == PRState.OPEN
        assert pr.closed_at is None
        assert pr.merged_at is None

    def test_create_pr_analytics_merged(self, db_session):
        """PRAnalytics can be created with state=MERGED and merged_at timestamp."""
        uid = self._add_user(db_session)
        opened = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        merged = datetime(2024, 1, 3, 17, 0, tzinfo=timezone.utc)

        pr = PRAnalytics(
            user_id=uid,
            github_pr_id=200,
            repo_name="org/repo",
            number=10,
            title="Merged PR",
            state=PRState.MERGED,
            opened_at=opened,
            merged_at=merged,
            review_count=1,
            comment_count=2,
            files_changed=5,
            lines_added=150,
            lines_deleted=30,
        )
        db_session.add(pr)
        db_session.flush()

        assert pr.state == PRState.MERGED
        assert pr.merged_at == merged

    def test_create_pr_analytics_closed(self, db_session):
        """PRAnalytics can be created with state=CLOSED and closed_at timestamp."""
        uid = self._add_user(db_session)
        pr = PRAnalytics(
            user_id=uid,
            github_pr_id=300,
            repo_name="org/repo",
            number=11,
            title="Closed PR",
            state=PRState.CLOSED,
            opened_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            closed_at=datetime(2024, 2, 2, tzinfo=timezone.utc),
            review_count=0,
            comment_count=1,
            files_changed=1,
            lines_added=10,
            lines_deleted=5,
        )
        db_session.add(pr)
        db_session.flush()
        assert pr.state == PRState.CLOSED
        assert pr.closed_at is not None

    def test_create_pr_analytics_draft(self, db_session):
        """PRAnalytics can be created with state=DRAFT."""
        uid = self._add_user(db_session)
        pr = PRAnalytics(
            user_id=uid,
            github_pr_id=400,
            repo_name="org/repo",
            number=12,
            title="Draft PR",
            state=PRState.DRAFT,
            opened_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            review_count=0,
            comment_count=0,
            files_changed=2,
            lines_added=20,
            lines_deleted=0,
        )
        db_session.add(pr)
        db_session.flush()
        assert pr.state == PRState.DRAFT

    def test_cycle_time_when_merged(self, db_session):
        """cycle_time returns correct seconds when merged_at is set."""
        uid = self._add_user(db_session)
        opened = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        merged = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)  # 8 hours later

        pr = PRAnalytics(
            user_id=uid,
            github_pr_id=500,
            repo_name="org/repo",
            number=20,
            title="Timed PR",
            state=PRState.MERGED,
            opened_at=opened,
            merged_at=merged,
            review_count=1,
            comment_count=0,
            files_changed=1,
            lines_added=10,
            lines_deleted=5,
        )
        db_session.add(pr)
        db_session.flush()

        assert pr.cycle_time == 8 * 3600  # 28800 seconds

    def test_cycle_time_when_not_merged(self, db_session):
        """cycle_time returns None when merged_at is not set."""
        uid = self._add_user(db_session)
        pr = make_pr_analytics(uid, github_pr_id=600)
        pr.merged_at = None
        db_session.add(pr)
        db_session.flush()

        assert pr.cycle_time is None

    def test_cycle_time_when_opened_at_none(self):
        """cycle_time returns None when opened_at is not set (transient model)."""
        pr = PRAnalytics()
        pr.merged_at = datetime(2024, 1, 2, tzinfo=timezone.utc)
        pr.opened_at = None

        assert pr.cycle_time is None

    def test_duplicate_github_pr_id_raises(self, db_session):
        """Two PRAnalytics rows with the same github_pr_id raises IntegrityError."""
        uid = self._add_user(db_session)

        db_session.add(make_pr_analytics(uid, github_pr_id=700))
        db_session.flush()

        db_session.add(make_pr_analytics(uid, github_pr_id=700))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_pr_analytics_repr(self, db_session):
        """__repr__ includes id and user_id."""
        uid = self._add_user(db_session)
        pr = make_pr_analytics(uid, github_pr_id=800)
        db_session.add(pr)
        db_session.flush()

        r = repr(pr)
        assert str(pr.id) in r
        assert str(uid) in r

    def test_all_pr_states_persist(self, db_session):
        """PRAnalytics rows with each PRState value can be persisted."""
        uid = self._add_user(db_session)

        for i, state in enumerate(PRState):
            pr = PRAnalytics(
                user_id=uid,
                github_pr_id=900 + i,
                repo_name="org/repo",
                number=50 + i,
                title=f"PR state {state.value}",
                state=state,
                opened_at=datetime(2024, 6, i + 1, tzinfo=timezone.utc),
                review_count=0,
                comment_count=0,
                files_changed=1,
                lines_added=1,
                lines_deleted=0,
            )
            db_session.add(pr)

        db_session.flush()  # Should not raise


class TestWeeklyLanguages:
    """Tests for the WeeklyLanguages model."""

    def _add_user(self, db_session) -> int:
        user = make_user()
        db_session.add(user)
        db_session.flush()
        return user.id

    def test_create_weekly_languages(self, db_session):
        """WeeklyLanguages can be created and persisted with all fields."""
        uid = self._add_user(db_session)
        week_start = datetime(2024, 1, 1, tzinfo=timezone.utc)

        wl = WeeklyLanguages(
            user_id=uid,
            language="Python",
            week_start=week_start,
            lines_written=1000,
            repo_count=5,
        )
        db_session.add(wl)
        db_session.flush()

        assert wl.id is not None
        assert wl.user_id == uid
        assert wl.language == "Python"
        assert wl.week_start == week_start
        assert wl.lines_written == 1000
        assert wl.repo_count == 5

    def test_unique_user_language_week_start(self, db_session):
        """Duplicate (user_id, language, week_start) raises IntegrityError."""
        uid = self._add_user(db_session)

        db_session.add(make_weekly_languages(uid))
        db_session.flush()

        db_session.add(make_weekly_languages(uid))
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_different_languages_same_week_allowed(self, db_session):
        """Same user can have different languages for the same week."""
        uid = self._add_user(db_session)
        week = datetime(2024, 1, 1, tzinfo=timezone.utc)

        db_session.add(
            WeeklyLanguages(
                user_id=uid,
                language="Python",
                week_start=week,
                lines_written=100,
                repo_count=1,
            )
        )
        db_session.add(
            WeeklyLanguages(
                user_id=uid,
                language="TypeScript",
                week_start=week,
                lines_written=200,
                repo_count=2,
            )
        )
        db_session.flush()  # Should not raise

    def test_same_language_different_weeks_allowed(self, db_session):
        """Same user and language can appear in different weeks."""
        uid = self._add_user(db_session)

        db_session.add(
            WeeklyLanguages(
                user_id=uid,
                language="Python",
                week_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
                lines_written=100,
                repo_count=1,
            )
        )
        db_session.add(
            WeeklyLanguages(
                user_id=uid,
                language="Python",
                week_start=datetime(2024, 1, 8, tzinfo=timezone.utc),
                lines_written=200,
                repo_count=1,
            )
        )
        db_session.flush()  # Should not raise

    def test_different_users_same_language_week_allowed(self, db_session):
        """Different users can have the same language and week_start."""
        u1 = make_user(
            authentik_sub="sub-wl1", email="wl1@example.com", github_username="gh-wl1"
        )
        u2 = make_user(
            authentik_sub="sub-wl2", email="wl2@example.com", github_username="gh-wl2"
        )
        db_session.add_all([u1, u2])
        db_session.flush()

        week = datetime(2024, 2, 1, tzinfo=timezone.utc)
        db_session.add(
            WeeklyLanguages(
                user_id=u1.id,
                language="Go",
                week_start=week,
                lines_written=50,
                repo_count=1,
            )
        )
        db_session.add(
            WeeklyLanguages(
                user_id=u2.id,
                language="Go",
                week_start=week,
                lines_written=75,
                repo_count=2,
            )
        )
        db_session.flush()  # Should not raise
