"""
Pydantic schemas for metric models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..models.metrics import PRState


class DailyStats(BaseModel):
    """
    Pydantic schema for daily user statistics.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to user table.
        date (datetime): Date for the statistics.
        commit_count (int): Number of commits.
        pr_opened_count (int): Number of PRs opened.
        pr_merged_count (int): Number of PRs merged.
        pr_reviewed_count (int): Number of PRs reviewed.
        issues_opened_count (int): Number of issues opened.
        lines_added_count (int): Number of lines added.
        lines_deleted_count (int): Number of lines deleted.
        repos_contributed_to_count (int): Number of repositories contributed to.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    date: datetime
    commit_count: int
    pr_opened_count: int
    pr_merged_count: int
    pr_reviewed_count: int
    issues_opened_count: int
    lines_added_count: int
    lines_deleted_count: int
    repos_contributed_to_count: int


class PRAnalytics(BaseModel):
    """
    Pydantic schema for pull request analytics.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to user table.
        github_pr_id (int): Unique GitHub PR ID.
        repo_name (str): Name of the repository.
        number (int): PR number.
        title (str): PR title.
        state (PRState): State of the PR.
        opened_at (datetime): When the PR was opened.
        closed_at (Optional[datetime]): When the PR was closed.
        merged_at (Optional[datetime]): When the PR was merged.
        review_count (int): Number of reviews.
        comment_count (int): Number of comments.
        files_changed (int): Number of files changed.
        lines_added (int): Number of lines added.
        lines_deleted (int): Number of lines deleted.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    github_pr_id: int
    repo_name: str
    number: int
    title: str
    state: PRState
    opened_at: datetime
    closed_at: Optional[datetime]
    merged_at: Optional[datetime]
    review_count: int
    comment_count: int
    files_changed: int
    lines_added: int
    lines_deleted: int


class WeeklyLanguages(BaseModel):
    """
    Pydantic schema for weekly language usage statistics.

    Attributes:
        id (int): Primary key.
        user_id (int): Foreign key to user table.
        language (str): Programming language name.
        week_start (datetime): Start of the week.
        lines_written (int): Number of lines written in the week.
        repo_count (int): Number of repositories contributed to in the week.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    language: str
    week_start: datetime
    lines_written: int
    repo_count: int
