"""GitLab SCM provider implementation."""

import logging
from datetime import datetime, timezone
from typing import Optional

from ...config import get_config_value
from ..scm_protocol import (
    SCMDeployment,
    SCMPullRequest,
    SCMRepository,
    SCMTeam,
)

logger = logging.getLogger(__name__)


class GitLabProvider:
    """GitLab implementation of the SCM provider protocol."""

    def __init__(self, token: Optional[str] = None, url: Optional[str] = None):
        self._token = token or get_config_value("GITLAB_TOKEN")
        self._url = url or get_config_value("GITLAB_URL") or "https://gitlab.com"
        self._client = None

    @property
    def provider_name(self) -> str:
        return "gitlab"

    @property
    def client(self):
        if self._client is None:
            try:
                import gitlab
            except ImportError:
                raise ImportError("python-gitlab is required: pip install python-gitlab")
            if not self._token:
                raise ValueError("GitLab token not configured")
            self._client = gitlab.Gitlab(self._url, private_token=self._token)
            self._client.auth()
        return self._client

    def get_repositories(self) -> list[SCMRepository]:
        repos = []
        for project in self.client.projects.list(membership=True, iterator=True):
            repos.append(SCMRepository(
                provider="gitlab",
                external_id=str(project.id),
                name=project.name,
                full_name=project.path_with_namespace,
                default_branch=project.default_branch or "main",
                url=project.web_url,
                is_active=not project.archived,
            ))
        return repos

    def get_pull_requests(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[SCMPullRequest]:
        results = []
        since_str = since.strftime("%Y-%m-%dT%H:%M:%SZ")
        until_str = until.strftime("%Y-%m-%dT%H:%M:%SZ")

        if repo_full_name:
            projects = [self.client.projects.get(repo_full_name)]
        else:
            projects = list(self.client.projects.list(membership=True, iterator=True))

        for project in projects:
            try:
                mrs = project.mergerequests.list(
                    created_after=since_str,
                    created_before=until_str,
                    state="all",
                    iterator=True,
                )
                for mr in mrs:
                    if author and mr.author.get("username") != author:
                        continue

                    created_at = datetime.fromisoformat(
                        mr.created_at.replace("Z", "+00:00")
                    )
                    merged_at = None
                    if mr.merged_at:
                        merged_at = datetime.fromisoformat(
                            mr.merged_at.replace("Z", "+00:00")
                        )
                    closed_at = None
                    if mr.closed_at:
                        closed_at = datetime.fromisoformat(
                            mr.closed_at.replace("Z", "+00:00")
                        )

                    if mr.state == "merged":
                        state = "merged"
                    elif mr.state == "closed":
                        state = "closed"
                    else:
                        state = "open"

                    changes = mr.changes_count or 0

                    results.append(SCMPullRequest(
                        provider="gitlab",
                        external_id=str(mr.id),
                        number=mr.iid,
                        title=mr.title,
                        state=state,
                        author=mr.author.get("username", ""),
                        base_branch=mr.target_branch,
                        head_branch=mr.source_branch,
                        created_at=created_at,
                        merged_at=merged_at,
                        closed_at=closed_at,
                        additions=0,
                        deletions=0,
                        changed_files=int(changes) if changes else 0,
                        commits_count=0,
                        review_count=0,
                        reviewer_count=len(mr.reviewers) if mr.reviewers else 0,
                        comment_count=mr.user_notes_count or 0,
                        is_revert="revert" in mr.title.lower(),
                        is_hotfix="hotfix" in mr.title.lower(),
                        labels=mr.labels or [],
                        reviewers=[r.get("username", "") for r in (mr.reviewers or [])],
                        repository_full_name=project.path_with_namespace,
                        url=mr.web_url,
                    ))
            except Exception as e:
                logger.warning("Error fetching MRs from %s: %s", project.path_with_namespace, e)

        return results

    def get_deployments(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[SCMDeployment]:
        results = []

        if repo_full_name:
            projects = [self.client.projects.get(repo_full_name)]
        else:
            projects = list(self.client.projects.list(membership=True, iterator=True))

        for project in projects:
            try:
                deployments = project.deployments.list(
                    updated_after=since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    updated_before=until.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    iterator=True,
                )
                for d in deployments:
                    if environment and d.environment != environment:
                        continue

                    deployed_at = datetime.fromisoformat(
                        d.created_at.replace("Z", "+00:00")
                    )
                    completed_at = None
                    if hasattr(d, "finished_at") and d.finished_at:
                        completed_at = datetime.fromisoformat(
                            d.finished_at.replace("Z", "+00:00")
                        )

                    results.append(SCMDeployment(
                        provider="gitlab",
                        external_id=str(d.id),
                        environment=d.environment,
                        ref=d.ref,
                        sha=d.sha,
                        status=d.status,
                        deployed_at=deployed_at,
                        completed_at=completed_at,
                        is_rollback=False,
                        triggered_by=d.user.get("username", "") if d.user else "",
                        repository_full_name=project.path_with_namespace,
                    ))
            except Exception as e:
                logger.debug("Error fetching deployments from %s: %s",
                             project.path_with_namespace, e)

        return results

    def get_teams(self) -> list[SCMTeam]:
        teams = []
        try:
            for group in self.client.groups.list(iterator=True):
                members = [m.username for m in group.members.list(iterator=True)]
                teams.append(SCMTeam(
                    provider="gitlab",
                    external_id=str(group.id),
                    name=group.name,
                    slug=group.path,
                    members=members,
                ))
        except Exception as e:
            logger.warning("Error fetching GitLab groups: %s", e)
        return teams
