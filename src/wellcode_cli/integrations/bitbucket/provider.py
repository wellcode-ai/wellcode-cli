"""Bitbucket SCM provider implementation."""

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


class BitbucketProvider:
    """Bitbucket Cloud implementation of the SCM provider protocol."""

    def __init__(
        self,
        username: Optional[str] = None,
        app_password: Optional[str] = None,
        workspace: Optional[str] = None,
    ):
        self._username = username or get_config_value("BITBUCKET_USERNAME")
        self._app_password = app_password or get_config_value("BITBUCKET_APP_PASSWORD")
        self._workspace = workspace or get_config_value("BITBUCKET_WORKSPACE")
        self._client = None

    @property
    def provider_name(self) -> str:
        return "bitbucket"

    @property
    def client(self):
        if self._client is None:
            try:
                from atlassian import Bitbucket
            except ImportError:
                raise ImportError(
                    "atlassian-python-api is required: pip install atlassian-python-api"
                )
            if not self._username or not self._app_password:
                raise ValueError("Bitbucket credentials not configured")
            self._client = Bitbucket(
                url="https://api.bitbucket.org",
                username=self._username,
                password=self._app_password,
                cloud=True,
            )
        return self._client

    def get_repositories(self) -> list[SCMRepository]:
        repos = []
        if not self._workspace:
            return repos

        try:
            data = self.client.get(
                f"/2.0/repositories/{self._workspace}",
                params={"pagelen": 100},
            )
            for r in data.get("values", []):
                mainbranch = r.get("mainbranch", {})
                repos.append(SCMRepository(
                    provider="bitbucket",
                    external_id=r.get("uuid", ""),
                    name=r.get("name", ""),
                    full_name=r.get("full_name", ""),
                    default_branch=mainbranch.get("name", "main") if mainbranch else "main",
                    url=r.get("links", {}).get("html", {}).get("href", ""),
                    is_active=True,
                ))
        except Exception as e:
            logger.warning("Error fetching Bitbucket repos: %s", e)
        return repos

    def get_pull_requests(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[SCMPullRequest]:
        results = []

        if repo_full_name:
            repo_slugs = [repo_full_name]
        elif self._workspace:
            repo_slugs = [r.full_name for r in self.get_repositories()]
        else:
            return results

        for repo_slug in repo_slugs:
            try:
                data = self.client.get(
                    f"/2.0/repositories/{repo_slug}/pullrequests",
                    params={"state": "ALL", "pagelen": 50},
                )
                for pr in data.get("values", []):
                    created_str = pr.get("created_on", "")
                    if not created_str:
                        continue
                    created_at = datetime.fromisoformat(
                        created_str.replace("Z", "+00:00")
                    )
                    if created_at < since.replace(tzinfo=timezone.utc):
                        break
                    if created_at > until.replace(tzinfo=timezone.utc):
                        continue

                    pr_author = pr.get("author", {}).get("display_name", "")
                    if author and pr_author != author:
                        continue

                    state_map = {"OPEN": "open", "MERGED": "merged", "DECLINED": "closed"}
                    state = state_map.get(pr.get("state", ""), "open")

                    merged_at = None
                    if pr.get("merge_commit") and pr.get("updated_on"):
                        merged_at = datetime.fromisoformat(
                            pr["updated_on"].replace("Z", "+00:00")
                        )

                    source = pr.get("source", {}).get("branch", {})
                    dest = pr.get("destination", {}).get("branch", {})

                    results.append(SCMPullRequest(
                        provider="bitbucket",
                        external_id=str(pr.get("id", "")),
                        number=pr.get("id", 0),
                        title=pr.get("title", ""),
                        state=state,
                        author=pr_author,
                        base_branch=dest.get("name", "main"),
                        head_branch=source.get("name", ""),
                        created_at=created_at,
                        merged_at=merged_at,
                        comment_count=pr.get("comment_count", 0),
                        is_revert="revert" in pr.get("title", "").lower(),
                        is_hotfix="hotfix" in pr.get("title", "").lower(),
                        repository_full_name=repo_slug,
                        url=pr.get("links", {}).get("html", {}).get("href", ""),
                    ))
            except Exception as e:
                logger.warning("Error fetching PRs from %s: %s", repo_slug, e)

        return results

    def get_deployments(
        self, since: datetime, until: datetime,
        repo_full_name: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[SCMDeployment]:
        # Bitbucket Pipelines don't have a direct deployments API like GitHub
        # We'd parse pipeline results for deployment steps
        return []

    def get_teams(self) -> list[SCMTeam]:
        teams = []
        if not self._workspace:
            return teams
        try:
            data = self.client.get(
                f"/1.0/groups/{self._workspace}",
            )
            for g in data if isinstance(data, list) else []:
                members = [m.get("username", "") for m in g.get("members", [])]
                teams.append(SCMTeam(
                    provider="bitbucket",
                    external_id=g.get("slug", ""),
                    name=g.get("name", ""),
                    slug=g.get("slug", ""),
                    members=members,
                ))
        except Exception as e:
            logger.debug("Error fetching Bitbucket teams: %s", e)
        return teams
