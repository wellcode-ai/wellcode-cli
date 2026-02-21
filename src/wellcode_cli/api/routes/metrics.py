"""PR and general engineering metrics API endpoints."""

import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ...db.engine import get_session
from ...db.repository import MetricStore

router = APIRouter()


class PRMetricsResponse(BaseModel):
    total_prs: int = 0
    merged_prs: int = 0
    open_prs: int = 0
    avg_cycle_time_hours: float = 0
    avg_time_to_merge_hours: float = 0
    avg_time_to_first_review_hours: float = 0
    avg_pr_size: float = 0
    revert_count: int = 0
    hotfix_count: int = 0
    self_merge_count: int = 0
    ai_assisted_count: int = 0
    top_contributors: list = []
    pr_size_distribution: dict = {}


class SnapshotResponse(BaseModel):
    id: int
    collected_at: str
    period_start: str
    period_end: str
    source: str
    status: str
    summary: Optional[dict] = None
    duration_seconds: Optional[float] = None


@router.get("/prs", response_model=PRMetricsResponse)
def get_pr_metrics(
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    repo_id: Optional[int] = None,
    author: Optional[str] = None,
):
    now = datetime.now(timezone.utc)
    end_dt = datetime.fromisoformat(end) if end else now
    start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(days=30)

    session = get_session()
    store = MetricStore(session)

    prs = store.pull_requests.get_by_period(start_dt, end_dt, repo_id=repo_id)

    if author:
        prs = [p for p in prs if p.author and p.author.username == author]

    merged = [p for p in prs if p.state == "merged"]
    open_prs = [p for p in prs if p.state == "open"]

    cycle_times = [p.cycle_time_hours for p in merged if p.cycle_time_hours]
    merge_times = [p.time_to_merge_hours for p in merged if p.time_to_merge_hours]
    review_times = [p.time_to_first_review_hours for p in prs if p.time_to_first_review_hours]
    sizes = [p.additions + p.deletions for p in prs if p.additions or p.deletions]

    # Top contributors
    contrib_counts = {}
    for p in prs:
        if p.author:
            contrib_counts[p.author.username] = contrib_counts.get(p.author.username, 0) + 1
    top = sorted(contrib_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Size distribution
    small = sum(1 for s in sizes if s < 100)
    medium = sum(1 for s in sizes if 100 <= s < 500)
    large = sum(1 for s in sizes if s >= 500)

    session.close()

    return PRMetricsResponse(
        total_prs=len(prs),
        merged_prs=len(merged),
        open_prs=len(open_prs),
        avg_cycle_time_hours=statistics.mean(cycle_times) if cycle_times else 0,
        avg_time_to_merge_hours=statistics.mean(merge_times) if merge_times else 0,
        avg_time_to_first_review_hours=statistics.mean(review_times) if review_times else 0,
        avg_pr_size=statistics.mean(sizes) if sizes else 0,
        revert_count=sum(1 for p in prs if p.is_revert),
        hotfix_count=sum(1 for p in prs if p.is_hotfix),
        self_merge_count=sum(1 for p in prs if p.is_self_merged),
        ai_assisted_count=sum(1 for p in prs if p.is_ai_generated),
        top_contributors=[{"username": u, "pr_count": c} for u, c in top],
        pr_size_distribution={"small": small, "medium": medium, "large": large},
    )


@router.get("/snapshots", response_model=list[SnapshotResponse])
def list_snapshots(limit: int = Query(20, le=100)):
    session = get_session()
    store = MetricStore(session)
    snaps = store.snapshots.list_recent(limit)
    result = [
        SnapshotResponse(
            id=s.id,
            collected_at=s.collected_at.isoformat() if s.collected_at else "",
            period_start=s.period_start.isoformat() if s.period_start else "",
            period_end=s.period_end.isoformat() if s.period_end else "",
            source=s.source or "",
            status=s.status or "",
            summary=s.summary,
            duration_seconds=s.duration_seconds,
        )
        for s in snaps
    ]
    session.close()
    return result
