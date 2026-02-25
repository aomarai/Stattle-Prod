from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy import Enum as SQLEnum

from . import Base


class PRState(Enum):
    """
    The main statuses that a pull request can exist in.
    """

    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class DailyStats(Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_user_date"),)

    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    commit_count: Mapped[int] = mapped_column(nullable=False)
    pr_opened_count: Mapped[int] = mapped_column(nullable=False)
    pr_merged_count: Mapped[int] = mapped_column(nullable=False)
    pr_reviewed_count: Mapped[int] = mapped_column(nullable=False)
    issues_opened_count: Mapped[int] = mapped_column(nullable=False)
    lines_added_count: Mapped[int] = mapped_column(nullable=False)
    lines_deleted_count: Mapped[int] = mapped_column(nullable=False)
    repos_contributed_to_count: Mapped[int] = mapped_column(nullable=False)


class PRAnalytics(Base):
    __tablename__ = "pr_analytics"
    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    github_pr_id: Mapped[int] = mapped_column(unique=True, nullable=False)
    repo_name: Mapped[str] = mapped_column(nullable=False)
    number: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    state: Mapped[PRState] = mapped_column(SQLEnum(PRState), nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_count: Mapped[int] = mapped_column(nullable=False)
    comment_count: Mapped[int] = mapped_column(nullable=False)
    files_changed: Mapped[int] = mapped_column(nullable=False)
    lines_added: Mapped[int] = mapped_column(nullable=False)
    lines_deleted: Mapped[int] = mapped_column(nullable=False)

    @property
    def cycle_time(self) -> Optional[float]:
        """
        Calculates how long it takes for a PR to go from opened to merged.

        :return: The cycle time in seconds, or None if the PR hasn't been merged.
        """
        if self.merged_at and self.opened_at:
            return (self.merged_at - self.opened_at).total_seconds()
        return None

    def __repr__(self) -> str:
        return f"PRAnalytics(id={self.id}, user_id={self.user_id})"


class WeeklyLanguages(Base):
    __tablename__ = "weekly_languages"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "language", "week_start", name="uq_user_language_week_start"
        ),
    )
    id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    language: Mapped[str] = mapped_column(nullable=False)
    week_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lines_written: Mapped[int] = mapped_column(nullable=False)
    repo_count: Mapped[int] = mapped_column(nullable=False)
