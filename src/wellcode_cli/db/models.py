"""SQLAlchemy models for persistent metric storage."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Reference / dimension tables
# ---------------------------------------------------------------------------

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    provider = Column(String(50), nullable=False)  # github, gitlab, bitbucket
    external_id = Column(String(255))
    avatar_url = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    repositories = relationship("Repository", back_populates="organization")
    teams = relationship("Team", back_populates="organization")


class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512))
    provider = Column(String(50), nullable=False)
    external_id = Column(String(255))
    default_branch = Column(String(100), default="main")
    url = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="repositories")
    pull_requests = relationship("PullRequestMetric", back_populates="repository")
    deployments = relationship("DeploymentMetric", back_populates="repository")

    __table_args__ = (
        UniqueConstraint("provider", "full_name", name="uq_repo_provider_name"),
    )


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255))
    provider = Column(String(50))
    external_id = Column(String(255))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="teams")
    members = relationship("TeamMember", back_populates="team")


class Developer(Base):
    __tablename__ = "developers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    display_name = Column(String(255))
    email = Column(String(255))
    provider = Column(String(50), nullable=False)
    external_id = Column(String(255))
    avatar_url = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    team_memberships = relationship("TeamMember", back_populates="developer")
    pull_requests = relationship("PullRequestMetric", back_populates="author",
                                 foreign_keys="PullRequestMetric.author_id")

    __table_args__ = (
        UniqueConstraint("provider", "username", name="uq_dev_provider_username"),
    )


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=False)
    role = Column(String(50), default="member")
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    team = relationship("Team", back_populates="members")
    developer = relationship("Developer", back_populates="team_memberships")


# ---------------------------------------------------------------------------
# Metric snapshot (each collection run)
# ---------------------------------------------------------------------------

class MetricSnapshot(Base):
    __tablename__ = "metric_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    collected_at = Column(DateTime, nullable=False,
                          default=lambda: datetime.now(timezone.utc))
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    source = Column(String(50))  # github, gitlab, jira, linear, etc.
    status = Column(String(20), default="completed")  # running, completed, failed
    summary = Column(JSON)
    duration_seconds = Column(Float)

    __table_args__ = (
        Index("ix_snapshot_period", "period_start", "period_end"),
    )


# ---------------------------------------------------------------------------
# Pull request metrics
# ---------------------------------------------------------------------------

class PullRequestMetric(Base):
    __tablename__ = "pr_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)
    author_id = Column(Integer, ForeignKey("developers.id"), nullable=True)

    provider = Column(String(50), nullable=False)
    external_id = Column(String(255))
    number = Column(Integer)
    title = Column(Text)
    state = Column(String(20))  # open, closed, merged
    base_branch = Column(String(255))
    head_branch = Column(String(255))

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    merged_at = Column(DateTime)
    closed_at = Column(DateTime)
    first_commit_at = Column(DateTime)
    first_review_at = Column(DateTime)

    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    changed_files = Column(Integer, default=0)
    commits_count = Column(Integer, default=0)

    # Calculated durations (hours)
    time_to_first_review_hours = Column(Float)
    time_to_merge_hours = Column(Float)
    coding_time_hours = Column(Float)
    review_time_hours = Column(Float)
    lead_time_hours = Column(Float)
    cycle_time_hours = Column(Float)

    review_count = Column(Integer, default=0)
    reviewer_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    review_cycles = Column(Integer, default=0)

    is_revert = Column(Boolean, default=False)
    is_hotfix = Column(Boolean, default=False)
    is_self_merged = Column(Boolean, default=False)
    is_ai_generated = Column(Boolean, default=False)
    ai_tool = Column(String(50))

    labels = Column(JSON)
    reviewers = Column(JSON)

    repository = relationship("Repository", back_populates="pull_requests")
    author = relationship("Developer", back_populates="pull_requests",
                          foreign_keys=[author_id])

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_pr_provider_extid"),
        Index("ix_pr_created", "created_at"),
        Index("ix_pr_merged", "merged_at"),
        Index("ix_pr_author", "author_id"),
        Index("ix_pr_repo", "repository_id"),
    )


# ---------------------------------------------------------------------------
# Deployment metrics (for DORA)
# ---------------------------------------------------------------------------

class DeploymentMetric(Base):
    __tablename__ = "deployment_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)

    provider = Column(String(50), nullable=False)
    external_id = Column(String(255))
    environment = Column(String(100))
    ref = Column(String(255))
    sha = Column(String(64))
    status = Column(String(30))  # success, failure, pending, in_progress

    deployed_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)

    is_rollback = Column(Boolean, default=False)
    is_failure = Column(Boolean, default=False)
    triggered_by = Column(String(255))  # user, ci, schedule
    pr_number = Column(Integer)

    repository = relationship("Repository", back_populates="deployments")

    __table_args__ = (
        Index("ix_deploy_time", "deployed_at"),
        Index("ix_deploy_repo", "repository_id"),
        Index("ix_deploy_env", "environment"),
    )


# ---------------------------------------------------------------------------
# Incident metrics (for DORA MTTR / Change Failure Rate)
# ---------------------------------------------------------------------------

class IncidentMetric(Base):
    __tablename__ = "incident_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)

    provider = Column(String(50))  # github_issues, pagerduty, opsgenie
    external_id = Column(String(255))
    title = Column(Text)
    severity = Column(String(20))  # p0, p1, p2, p3, p4

    opened_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime)
    time_to_recovery_hours = Column(Float)

    deployment_id = Column(Integer, ForeignKey("deployment_metrics.id"), nullable=True)
    caused_by_change = Column(Boolean, default=False)
    root_cause = Column(Text)

    __table_args__ = (
        Index("ix_incident_opened", "opened_at"),
    )


# ---------------------------------------------------------------------------
# AI usage metrics
# ---------------------------------------------------------------------------

class AIUsageMetric(Base):
    __tablename__ = "ai_usage_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=True)

    tool = Column(String(50), nullable=False)  # copilot, cursor, claude_code, aider
    date = Column(DateTime, nullable=False)

    suggestions_shown = Column(Integer, default=0)
    suggestions_accepted = Column(Integer, default=0)
    lines_suggested = Column(Integer, default=0)
    lines_accepted = Column(Integer, default=0)
    active_users = Column(Integer, default=0)

    language = Column(String(50))
    editor = Column(String(50))
    model = Column(String(100))

    chat_sessions = Column(Integer, default=0)
    chat_messages = Column(Integer, default=0)
    inline_completions = Column(Integer, default=0)

    cost_usd = Column(Float, default=0.0)

    metadata_ = Column("metadata", JSON)

    __table_args__ = (
        Index("ix_ai_date", "date"),
        Index("ix_ai_tool", "tool"),
        Index("ix_ai_dev", "developer_id"),
    )


# ---------------------------------------------------------------------------
# Issue tracker metrics (JIRA / Linear)
# ---------------------------------------------------------------------------

class IssueMetric(Base):
    __tablename__ = "issue_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)

    provider = Column(String(50), nullable=False)  # jira, linear
    external_id = Column(String(255))
    project_key = Column(String(50))
    issue_type = Column(String(50))
    priority = Column(String(50))
    status = Column(String(50))
    status_category = Column(String(20))

    assignee = Column(String(255))
    reporter = Column(String(255))

    created_at = Column(DateTime)
    started_at = Column(DateTime)
    resolved_at = Column(DateTime)

    story_points = Column(Float)
    cycle_time_hours = Column(Float)
    time_to_start_hours = Column(Float)
    time_in_progress_hours = Column(Float)

    sprint_id = Column(String(100))
    sprint_name = Column(String(255))
    labels = Column(JSON)
    components = Column(JSON)

    __table_args__ = (
        Index("ix_issue_created", "created_at"),
        Index("ix_issue_provider", "provider"),
        Index("ix_issue_project", "project_key"),
    )


# ---------------------------------------------------------------------------
# DX Survey models
# ---------------------------------------------------------------------------

class Survey(Base):
    __tablename__ = "surveys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    survey_type = Column(String(50))  # pulse, full_dx, custom
    status = Column(String(20), default="draft")  # draft, active, closed

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    starts_at = Column(DateTime)
    ends_at = Column(DateTime)
    recurrence = Column(String(20))  # none, weekly, monthly

    target_teams = Column(JSON)
    target_roles = Column(JSON)

    questions = relationship("SurveyQuestion", back_populates="survey")
    responses = relationship("SurveyResponse", back_populates="survey")


class SurveyQuestion(Base):
    __tablename__ = "survey_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(30), nullable=False)  # rating, multiple_choice, text
    options = Column(JSON)
    order = Column(Integer, default=0)
    required = Column(Boolean, default=True)
    category = Column(String(50))

    survey = relationship("Survey", back_populates="questions")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    survey_id = Column(Integer, ForeignKey("surveys.id"), nullable=False)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=True)

    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    answers = Column(JSON, nullable=False)
    sentiment_score = Column(Float)

    survey = relationship("Survey", back_populates="responses")


# ---------------------------------------------------------------------------
# DORA aggregated snapshots
# ---------------------------------------------------------------------------

class DORASnapshot(Base):
    __tablename__ = "dora_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(Integer, ForeignKey("metric_snapshots.id"), nullable=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=True)

    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    deployment_frequency = Column(Float)  # deploys per day
    lead_time_hours = Column(Float)  # median lead time for changes
    change_failure_rate = Column(Float)  # percentage
    mttr_hours = Column(Float)  # mean time to recovery

    level = Column(String(20))  # elite, high, medium, low

    details = Column(JSON)

    __table_args__ = (
        Index("ix_dora_period", "period_start", "period_end"),
    )
