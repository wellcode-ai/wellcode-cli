"""DORA metrics calculation service.

Computes the four key DORA metrics:
- Deployment Frequency
- Lead Time for Changes
- Change Failure Rate
- Mean Time to Recovery (MTTR)
"""

import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..db.models import (
    DORASnapshot,
)
from ..db.repository import MetricStore

DORA_THRESHOLDS = {
    "deployment_frequency": {
        "elite": 1.0,       # multiple deploys per day (>=1/day)
        "high": 1 / 7,      # weekly to daily
        "medium": 1 / 30,   # monthly to weekly
    },
    "lead_time_hours": {
        "elite": 1,          # less than one hour
        "high": 24,           # less than one day
        "medium": 24 * 7,    # less than one week
    },
    "change_failure_rate": {
        "elite": 0.15,       # 0-15%
        "high": 0.30,        # 16-30%
        "medium": 0.45,      # 31-45%
    },
    "mttr_hours": {
        "elite": 1,
        "high": 24,
        "medium": 24 * 7,
    },
}


@dataclass
class DORAMetrics:
    deployment_frequency: float  # deploys per day
    lead_time_hours: float       # median hours from first commit to deploy
    change_failure_rate: float   # percentage 0-1
    mttr_hours: float            # mean time to recovery in hours
    level: str                   # elite, high, medium, low
    details: dict


def classify_dora_level(metrics: DORAMetrics) -> str:
    """Classify overall DORA performance level."""
    scores = []

    df = metrics.deployment_frequency
    if df >= DORA_THRESHOLDS["deployment_frequency"]["elite"]:
        scores.append(4)
    elif df >= DORA_THRESHOLDS["deployment_frequency"]["high"]:
        scores.append(3)
    elif df >= DORA_THRESHOLDS["deployment_frequency"]["medium"]:
        scores.append(2)
    else:
        scores.append(1)

    lt = metrics.lead_time_hours
    if lt <= DORA_THRESHOLDS["lead_time_hours"]["elite"]:
        scores.append(4)
    elif lt <= DORA_THRESHOLDS["lead_time_hours"]["high"]:
        scores.append(3)
    elif lt <= DORA_THRESHOLDS["lead_time_hours"]["medium"]:
        scores.append(2)
    else:
        scores.append(1)

    cfr = metrics.change_failure_rate
    if cfr <= DORA_THRESHOLDS["change_failure_rate"]["elite"]:
        scores.append(4)
    elif cfr <= DORA_THRESHOLDS["change_failure_rate"]["high"]:
        scores.append(3)
    elif cfr <= DORA_THRESHOLDS["change_failure_rate"]["medium"]:
        scores.append(2)
    else:
        scores.append(1)

    mttr = metrics.mttr_hours
    if mttr <= DORA_THRESHOLDS["mttr_hours"]["elite"]:
        scores.append(4)
    elif mttr <= DORA_THRESHOLDS["mttr_hours"]["high"]:
        scores.append(3)
    elif mttr <= DORA_THRESHOLDS["mttr_hours"]["medium"]:
        scores.append(2)
    else:
        scores.append(1)

    avg = sum(scores) / len(scores)
    if avg >= 3.5:
        return "elite"
    elif avg >= 2.5:
        return "high"
    elif avg >= 1.5:
        return "medium"
    return "low"


def compute_dora(
    store: MetricStore,
    period_start: datetime,
    period_end: datetime,
    repo_id: Optional[int] = None,
    team_id: Optional[int] = None,
) -> DORAMetrics:
    """Compute DORA metrics from stored data for a given period."""
    days = max((period_end - period_start).total_seconds() / 86400, 1)

    # --- Deployment Frequency ---
    deployments = store.deployments.get_by_period(
        period_start, period_end, repo_id=repo_id, environment="production"
    )
    if not deployments:
        deployments = store.deployments.get_by_period(
            period_start, period_end, repo_id=repo_id
        )
    successful_deploys = [d for d in deployments if d.status in ("success", "active")]
    deploy_freq = len(successful_deploys) / days if days > 0 else 0

    # Fallback: use merged PRs to main as proxy for deployments
    if not deployments:
        merged_prs = store.pull_requests.get_merged_by_period(
            period_start, period_end, repo_id=repo_id
        )
        main_merges = [p for p in merged_prs if p.base_branch in ("main", "master")]
        deploy_freq = len(main_merges) / days if days > 0 else 0
        successful_deploys = main_merges

    # --- Lead Time for Changes ---
    merged_prs = store.pull_requests.get_merged_by_period(
        period_start, period_end, repo_id=repo_id
    )
    lead_times = []
    for pr in merged_prs:
        if pr.lead_time_hours is not None:
            lead_times.append(pr.lead_time_hours)
        elif pr.first_commit_at and pr.merged_at:
            lt = (pr.merged_at - pr.first_commit_at).total_seconds() / 3600
            lead_times.append(lt)
        elif pr.created_at and pr.merged_at:
            lt = (pr.merged_at - pr.created_at).total_seconds() / 3600
            lead_times.append(lt)

    median_lead_time = statistics.median(lead_times) if lead_times else 0

    # --- Change Failure Rate ---
    total_deploys = len(successful_deploys) if successful_deploys else len(merged_prs)
    incidents = store.incidents.get_by_period(period_start, period_end)
    change_incidents = [i for i in incidents if i.caused_by_change]
    failed_deploys = [d for d in deployments if d.is_failure or d.is_rollback]

    failure_count = len(change_incidents) + len(failed_deploys)
    reverts = sum(1 for pr in merged_prs if pr.is_revert)
    hotfixes = sum(1 for pr in merged_prs if pr.is_hotfix)
    failure_count += reverts

    cfr = failure_count / total_deploys if total_deploys > 0 else 0

    # --- Mean Time to Recovery ---
    recovery_times = []
    for incident in incidents:
        if incident.time_to_recovery_hours is not None:
            recovery_times.append(incident.time_to_recovery_hours)
        elif incident.resolved_at and incident.opened_at:
            rt = (incident.resolved_at - incident.opened_at).total_seconds() / 3600
            recovery_times.append(rt)

    mttr = statistics.mean(recovery_times) if recovery_times else 0

    metrics = DORAMetrics(
        deployment_frequency=deploy_freq,
        lead_time_hours=median_lead_time,
        change_failure_rate=min(cfr, 1.0),
        mttr_hours=mttr,
        level="",
        details={
            "total_deployments": len(deployments),
            "successful_deployments": len(successful_deploys),
            "failed_deployments": len(failed_deploys),
            "total_merged_prs": len(merged_prs),
            "reverts": reverts,
            "hotfixes": hotfixes,
            "incidents": len(incidents),
            "change_incidents": len(change_incidents),
            "lead_times_count": len(lead_times),
            "recovery_times_count": len(recovery_times),
            "period_days": days,
        },
    )
    metrics.level = classify_dora_level(metrics)

    # Persist the snapshot
    dora_snap = DORASnapshot(
        repository_id=repo_id,
        team_id=team_id,
        period_start=period_start,
        period_end=period_end,
        deployment_frequency=deploy_freq,
        lead_time_hours=median_lead_time,
        change_failure_rate=cfr,
        mttr_hours=mttr,
        level=metrics.level,
        details=metrics.details,
    )
    store.dora.save(dora_snap)
    store.commit()

    return metrics
