"""GitHub SCM provider implementation using the unified interface."""

import logging
from datetime import datetime, timezone
from typing import Optional

from github import Github

from ...config import get_config_value
from ..scm_protocol import (
    SCMDeployment,
    SCMProvider,
    SCMPullRequest,
    SCMRepository,
    SCMTeam,
)

logger = logging.getLogger(__name__)


class GitHubProvider:
    """GitHub implementation of the SCM provider protocol."""

    def __init__(self, token: Optional[str] = None, org: Optional[str] = None):
        self._token = token or get_config_value("GITHUB_TOKEN") or get_config_value("GITHUB_USER_TOKEN")
        self._org = org or get_config_value("GITHUB_ORG")
        self._client: Optional[Github] = None

    @property
    def provider_name(self) -> str:
        return "github"

    @property
    def client(self) -> Github:
        if self._client is None:
            if not self._token:
                raise ValueError("GitHub token not configured")
            self._client = Github(self._token)
        return self._client

    def get_repositories(self) -> list[SCMRepository]:
        repos = []
        if self._org:
            org = self.client.get_organization(self._org)
            gh_repos = org.get_repos()
        else:
            gh_repos = self.client.get_user().get_repos()

        for r in gh_repos:
            repos.append(SCMRepository(
                provider="github",
                external_id=str(r.id),
                name=r.name,
                full_name=r.full_name,
                default_branch=r.default_branch or "main",
                url=r.html_url,
                is_active=not r.archived,
            ))
        return repos

    def get_pull_requests(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[SCMPullRequest]:
        results = []

        if repo_full_name:
            repo_list = [self.client.get_repo(repo_full_name)]
        elif self._org:
            repo_list = list(self.client.get_organization(self._org).get_repos())
        else:
            repo_list = list(self.client.get_user().get_repos())

        since_utc = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
        until_utc = until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until

        for repo in repo_list:
            try:
                for pr in repo.get_pulls(state="all", sort="updated", direction="desc"):
                    created = pr.created_at.replace(tzinfo=timezone.utc) if pr.created_at.tzinfo is None else pr.created_at
                    if created < since_utc:
                        break
                    if created > until_utc:
                        continue
                    if author and pr.user.login != author:
                        continue

                    merged_at = None
                    if pr.merged_at:
                        merged_at = pr.merged_at.replace(tzinfo=timezone.utc) if pr.merged_at.tzinfo is None else pr.merged_at

                    state = "merged" if pr.merged else ("closed" if pr.state == "closed" else "open")

                    first_commit_at = None
                    if pr.merged:
                        try:
                            commits = list(pr.get_commits())
                            if commits:
                                fc = commits[0].commit.author.date
                                first_commit_at = fc.replace(tzinfo=timezone.utc) if fc.tzinfo is None else fc
                        except Exception:
                            pass

                    reviews = []
                    try:
                        reviews = list(pr.get_reviews())
                    except Exception:
                        pass

                    first_review_at = None
                    if reviews:
                        fr = min(r.submitted_at for r in reviews if r.submitted_at)
                        first_review_at = fr.replace(tzinfo=timezone.utc) if fr.tzinfo is None else fr

                    review_cycles = sum(1 for r in reviews if r.state == "CHANGES_REQUESTED")
                    reviewer_set = {r.user.login for r in reviews if r.user}

                    is_self_merged = (
                        pr.merged and pr.merged_by is not None
                        and pr.user.login == pr.merged_by.login
                    )

                    results.append(SCMPullRequest(
                        provider="github",
                        external_id=str(pr.id),
                        number=pr.number,
                        title=pr.title,
                        state=state,
                        author=pr.user.login,
                        base_branch=pr.base.ref,
                        head_branch=pr.head.ref,
                        created_at=created,
                        updated_at=pr.updated_at,
                        merged_at=merged_at,
                        closed_at=pr.closed_at,
                        first_commit_at=first_commit_at,
                        first_review_at=first_review_at,
                        additions=pr.additions,
                        deletions=pr.deletions,
                        changed_files=pr.changed_files,
                        commits_count=pr.commits,
                        review_count=len(reviews),
                        reviewer_count=len(reviewer_set),
                        comment_count=pr.comments + pr.review_comments,
                        review_cycles=review_cycles,
                        is_revert="revert" in pr.title.lower(),
                        is_hotfix="hotfix" in pr.title.lower() or any(
                            l.name.lower() == "hotfix" for l in pr.labels
                        ),
                        is_self_merged=is_self_merged,
                        labels=[l.name for l in pr.labels],
                        reviewers=list(reviewer_set),
                        repository_full_name=repo.full_name,
                        url=pr.html_url,
                    ))
            except Exception as e:
                logger.warning("Error fetching PRs from %s: %s", repo.full_name, e)

        return results

    def get_deployments(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[SCMDeployment]:
        results = []

        if repo_full_name:
            repo_list = [self.client.get_repo(repo_full_name)]
        elif self._org:
            repo_list = list(self.client.get_organization(self._org).get_repos())
        else:
            repo_list = list(self.client.get_user().get_repos())

        since_utc = since.replace(tzinfo=timezone.utc) if since.tzinfo is None else since
        until_utc = until.replace(tzinfo=timezone.utc) if until.tzinfo is None else until

        for repo in repo_list:
            try:
                for deploy in repo.get_deployments():
                    created = deploy.created_at.replace(tzinfo=timezone.utc) if deploy.created_at.tzinfo is None else deploy.created_at
                    if created < since_utc:
                        break
                    if created > until_utc:
                        continue

                    env = deploy.environment
                    if environment and env != environment:
                        continue

                    statuses = list(deploy.get_statuses())
                    status = statuses[0].state if statuses else "pending"
                    completed_at = statuses[0].created_at if statuses else None

                    duration = None
                    if completed_at:
                        completed_at = completed_at.replace(tzinfo=timezone.utc) if completed_at.tzinfo is None else completed_at
                        duration = (completed_at - created).total_seconds()

                    results.append(SCMDeployment(
                        provider="github",
                        external_id=str(deploy.id),
                        environment=env,
                        ref=deploy.ref,
                        sha=deploy.sha,
                        status=status,
                        deployed_at=created,
                        completed_at=completed_at,
                        duration_seconds=duration,
                        is_rollback=False,
                        triggered_by=deploy.creator.login if deploy.creator else "",
                        repository_full_name=repo.full_name,
                    ))
            except Exception as e:
                logger.debug("Error fetching deployments from %s: %s", repo.full_name, e)

        return results

    def get_teams(self) -> list[SCMTeam]:
        if not self._org:
            return []
        teams = []
        org = self.client.get_organization(self._org)
        for t in org.get_teams():
            members = [m.login for m in t.get_members()]
            teams.append(SCMTeam(
                provider="github",
                external_id=str(t.id),
                name=t.name,
                slug=t.slug,
                members=members,
            ))
        return teams
