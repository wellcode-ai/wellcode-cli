"""Metric collection orchestrator.

Pulls data from all configured SCM providers and stores it in the database.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ..config import get_config_value
from ..db.engine import get_session, init_db
from ..db.models import PullRequestMetric, DeploymentMetric
from ..db.repository import MetricStore
from ..integrations.scm_protocol import SCMProvider

logger = logging.getLogger(__name__)


def _get_configured_providers() -> list[SCMProvider]:
    """Discover and instantiate all configured SCM providers."""
    providers = []

    token = get_config_value("GITHUB_TOKEN") or get_config_value("GITHUB_USER_TOKEN")
    if token:
        from ..integrations.github.provider import GitHubProvider
        providers.append(GitHubProvider())

    if get_config_value("GITLAB_TOKEN"):
        from ..integrations.gitlab.provider import GitLabProvider
        providers.append(GitLabProvider())

    if get_config_value("BITBUCKET_USERNAME") and get_config_value("BITBUCKET_APP_PASSWORD"):
        from ..integrations.bitbucket.provider import BitbucketProvider
        providers.append(BitbucketProvider())

    return providers


def collect_all(
    period_start: datetime,
    period_end: datetime,
    providers: Optional[list[SCMProvider]] = None,
) -> dict:
    """Run a full metric collection cycle for the given period."""
    init_db()
    session = get_session()
    store = MetricStore(session)

    start_time = time.time()
    snapshot = store.snapshots.create(period_start, period_end)

    if providers is None:
        providers = _get_configured_providers()

    if not providers:
        logger.warning("No SCM providers configured")
        store.snapshots.fail(snapshot, "No SCM providers configured")
        store.commit()
        store.close()
        return {"error": "No SCM providers configured"}

    summary = {
        "providers": [],
        "total_prs": 0,
        "total_deployments": 0,
        "total_repos": 0,
    }

    for provider in providers:
        provider_name = provider.provider_name
        logger.info("Collecting from %s...", provider_name)
        prov_summary = {"name": provider_name, "prs": 0, "deployments": 0, "repos": 0}

        try:
            # Collect repositories
            repos = provider.get_repositories()
            for repo in repos:
                store.repositories.get_or_create(
                    full_name=repo.full_name,
                    provider=repo.provider,
                    default_branch=repo.default_branch,
                    url=repo.url,
                )
            prov_summary["repos"] = len(repos)
            store.commit()

            # Collect PRs
            prs = provider.get_pull_requests(period_start, period_end)
            for scm_pr in prs:
                repo = store.repositories.get_or_create(
                    full_name=scm_pr.repository_full_name,
                    provider=scm_pr.provider,
                )
                author = store.developers.get_or_create(
                    username=scm_pr.author,
                    provider=scm_pr.provider,
                )

                # Calculate durations
                ttfr = None
                if scm_pr.first_review_at and scm_pr.created_at:
                    ttfr = (scm_pr.first_review_at - scm_pr.created_at).total_seconds() / 3600

                ttm = None
                if scm_pr.merged_at and scm_pr.created_at:
                    ttm = (scm_pr.merged_at - scm_pr.created_at).total_seconds() / 3600

                coding_time = None
                if scm_pr.first_commit_at and scm_pr.first_review_at:
                    coding_time = (scm_pr.first_review_at - scm_pr.first_commit_at).total_seconds() / 3600

                lead_time = None
                if scm_pr.first_commit_at and scm_pr.merged_at:
                    lead_time = (scm_pr.merged_at - scm_pr.first_commit_at).total_seconds() / 3600

                from .ai_metrics import detect_ai_tool_from_pr
                ai_tool = detect_ai_tool_from_pr(
                    scm_pr.title, scm_pr.labels,
                )

                pr_metric = PullRequestMetric(
                    snapshot_id=snapshot.id,
                    repository_id=repo.id,
                    author_id=author.id,
                    provider=scm_pr.provider,
                    external_id=scm_pr.external_id,
                    number=scm_pr.number,
                    title=scm_pr.title,
                    state=scm_pr.state,
                    base_branch=scm_pr.base_branch,
                    head_branch=scm_pr.head_branch,
                    created_at=scm_pr.created_at,
                    updated_at=scm_pr.updated_at,
                    merged_at=scm_pr.merged_at,
                    closed_at=scm_pr.closed_at,
                    first_commit_at=scm_pr.first_commit_at,
                    first_review_at=scm_pr.first_review_at,
                    additions=scm_pr.additions,
                    deletions=scm_pr.deletions,
                    changed_files=scm_pr.changed_files,
                    commits_count=scm_pr.commits_count,
                    time_to_first_review_hours=ttfr,
                    time_to_merge_hours=ttm,
                    coding_time_hours=coding_time,
                    lead_time_hours=lead_time,
                    cycle_time_hours=lead_time,
                    review_count=scm_pr.review_count,
                    reviewer_count=scm_pr.reviewer_count,
                    comment_count=scm_pr.comment_count,
                    review_cycles=scm_pr.review_cycles,
                    is_revert=scm_pr.is_revert,
                    is_hotfix=scm_pr.is_hotfix,
                    is_self_merged=scm_pr.is_self_merged,
                    is_ai_generated=ai_tool is not None,
                    ai_tool=ai_tool,
                    labels=scm_pr.labels,
                    reviewers=scm_pr.reviewers,
                )
                store.pull_requests.upsert(pr_metric)

            prov_summary["prs"] = len(prs)
            store.commit()

            # Collect deployments
            deploys = provider.get_deployments(period_start, period_end)
            for scm_deploy in deploys:
                repo = store.repositories.get_or_create(
                    full_name=scm_deploy.repository_full_name,
                    provider=scm_deploy.provider,
                )
                deploy_metric = DeploymentMetric(
                    snapshot_id=snapshot.id,
                    repository_id=repo.id,
                    provider=scm_deploy.provider,
                    external_id=scm_deploy.external_id,
                    environment=scm_deploy.environment,
                    ref=scm_deploy.ref,
                    sha=scm_deploy.sha,
                    status=scm_deploy.status,
                    deployed_at=scm_deploy.deployed_at,
                    completed_at=scm_deploy.completed_at,
                    duration_seconds=scm_deploy.duration_seconds,
                    is_rollback=scm_deploy.is_rollback,
                    triggered_by=scm_deploy.triggered_by,
                    pr_number=scm_deploy.pr_number,
                )
                store.deployments.add(deploy_metric)

            prov_summary["deployments"] = len(deploys)
            store.commit()

            # Collect teams
            try:
                teams = provider.get_teams()
                for scm_team in teams:
                    org = None
                    if hasattr(provider, "_org") and provider._org:
                        org = store.organizations.get_or_create(
                            name=provider._org, provider=provider.provider_name
                        )
                    store.teams.get_or_create(
                        name=scm_team.name,
                        org_id=org.id if org else None,
                        slug=scm_team.slug,
                        provider=scm_team.provider,
                        external_id=scm_team.external_id,
                    )
                    for member_name in scm_team.members:
                        store.developers.get_or_create(
                            username=member_name, provider=scm_team.provider,
                        )
                store.commit()
            except Exception as e:
                logger.debug("Could not collect teams from %s: %s", provider_name, e)

        except Exception as e:
            logger.error("Error collecting from %s: %s", provider_name, e)
            prov_summary["error"] = str(e)

        summary["providers"].append(prov_summary)
        summary["total_prs"] += prov_summary["prs"]
        summary["total_deployments"] += prov_summary["deployments"]
        summary["total_repos"] += prov_summary["repos"]

    # Collect Copilot metrics if GitHub org is configured
    github_org = get_config_value("GITHUB_ORG")
    if github_org:
        from .ai_metrics import collect_copilot_metrics
        try:
            copilot_data = collect_copilot_metrics(
                store, github_org, period_start, period_end, snapshot.id,
            )
            summary["copilot_days"] = len(copilot_data)
        except Exception as e:
            logger.debug("Could not collect Copilot metrics: %s", e)

    duration = time.time() - start_time
    store.snapshots.complete(snapshot, summary, duration)
    store.commit()
    store.close()

    logger.info(
        "Collection complete: %d PRs, %d deployments in %.1fs",
        summary["total_prs"], summary["total_deployments"], duration,
    )
    return summary
