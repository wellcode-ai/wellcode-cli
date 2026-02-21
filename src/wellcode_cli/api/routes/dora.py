"""DORA metrics API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...db.engine import get_session
from ...db.repository import MetricStore
from ...services.dora import DORA_THRESHOLDS, compute_dora

router = APIRouter()


class DORAResponse(BaseModel):
    deployment_frequency: float
    lead_time_hours: float
    change_failure_rate: float
    mttr_hours: float
    level: str
    details: dict
    thresholds: dict = DORA_THRESHOLDS


class DORAHistoryItem(BaseModel):
    period_start: str
    period_end: str
    deployment_frequency: float
    lead_time_hours: float
    change_failure_rate: float
    mttr_hours: float
    level: str


@router.get("", response_model=DORAResponse)
def get_dora_metrics(
    start: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    repo_id: Optional[int] = None,
    team_id: Optional[int] = None,
):
    now = datetime.now(timezone.utc)
    end_dt = datetime.fromisoformat(end) if end else now
    start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(days=30)

    session = get_session()
    store = MetricStore(session)

    metrics = compute_dora(store, start_dt, end_dt, repo_id=repo_id, team_id=team_id)

    session.close()
    return DORAResponse(
        deployment_frequency=metrics.deployment_frequency,
        lead_time_hours=metrics.lead_time_hours,
        change_failure_rate=metrics.change_failure_rate,
        mttr_hours=metrics.mttr_hours,
        level=metrics.level,
        details=metrics.details,
    )


@router.get("/history", response_model=list[DORAHistoryItem])
def get_dora_history(
    limit: int = Query(30, le=100),
    team_id: Optional[int] = None,
):
    session = get_session()
    store = MetricStore(session)
    items = store.dora.get_history(limit=limit, team_id=team_id)
    result = [
        DORAHistoryItem(
            period_start=d.period_start.isoformat() if d.period_start else "",
            period_end=d.period_end.isoformat() if d.period_end else "",
            deployment_frequency=d.deployment_frequency or 0,
            lead_time_hours=d.lead_time_hours or 0,
            change_failure_rate=d.change_failure_rate or 0,
            mttr_hours=d.mttr_hours or 0,
            level=d.level or "low",
        )
        for d in items
    ]
    session.close()
    return result
