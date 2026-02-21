"""Protocol defining the unified SCM (Source Code Management) provider interface."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable


@dataclass
class SCMPullRequest:
    """Unified pull request / merge request representation."""
    provider: str
    external_id: str
    number: int
    title: str
    state: str  # open, closed, merged
    author: str
    base_branch: str
    head_branch: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    first_commit_at: Optional[datetime] = None
    first_review_at: Optional[datetime] = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    commits_count: int = 0
    review_count: int = 0
    reviewer_count: int = 0
    comment_count: int = 0
    review_cycles: int = 0
    is_revert: bool = False
    is_hotfix: bool = False
    is_self_merged: bool = False
    labels: list = field(default_factory=list)
    reviewers: list = field(default_factory=list)
    repository_full_name: str = ""
    url: str = ""


@dataclass
class SCMDeployment:
    """Unified deployment event."""
    provider: str
    external_id: str
    environment: str
    ref: str
    sha: str
    status: str  # success, failure, pending
    deployed_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    is_rollback: bool = False
    triggered_by: str = ""
    pr_number: Optional[int] = None
    repository_full_name: str = ""


@dataclass
class SCMRepository:
    """Unified repository representation."""
    provider: str
    external_id: str
    name: str
    full_name: str
    default_branch: str = "main"
    url: str = ""
    is_active: bool = True


@dataclass
class SCMTeam:
    provider: str
    external_id: str
    name: str
    slug: str
    members: list = field(default_factory=list)


@dataclass
class SCMReview:
    provider: str
    reviewer: str
    state: str  # approved, changes_requested, commented
    submitted_at: datetime
    body: str = ""
    pr_number: int = 0


@runtime_checkable
class SCMProvider(Protocol):
    """Protocol that all SCM integrations must implement."""

    @property
    def provider_name(self) -> str: ...

    def get_repositories(self) -> list[SCMRepository]: ...

    def get_pull_requests(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[SCMPullRequest]: ...

    def get_deployments(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[SCMDeployment]: ...

    def get_teams(self) -> list[SCMTeam]: ...
