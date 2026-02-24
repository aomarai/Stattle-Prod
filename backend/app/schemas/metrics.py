from datetime import datetime

from pydantic import BaseModel

from ..models.metrics import PRState

class DailyStats(BaseModel):
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
    id: int
    user_id: int
    github_pr_id: int
    repo_name: str
    number: int
    title: str
    state: PRState
    opened_at: datetime
    closed_at: datetime
    merged_at: datetime
    review_count: int
    comment_count: int
    files_changed: int
    lines_added: int
    lines_deleted: int

class WeeklyLanguages(BaseModel):
    id: int
    user_id: int
    language: str
    week_start: datetime
    lines_written: int
    repo_count: int