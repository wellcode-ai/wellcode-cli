"""AI coding tool metrics API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ...db.engine import get_session
from ...db.repository import MetricStore
from ...services.ai_metrics import compute_ai_impact

router = APIRouter()


class AIToolMetric(BaseModel):
    tool: str
    total_suggestions_shown: int
    total_suggestions_accepted: int
    total_lines_accepted: int
    active_users: int
    acceptance_rate: float
    total_cost_usd: float


class AIImpactResponse(BaseModel):
    ai_assisted_pr_count: int
    non_ai_pr_count: int
    ai_avg_cycle_time_hours: float
    non_ai_avg_cycle_time_hours: float
    ai_avg_review_time_hours: float
    non_ai_avg_review_time_hours: float
    ai_revert_rate: float
    non_ai_revert_rate: float
    productivity_change_pct: float
    tools: list[AIToolMetric]


class AIUsageDayResponse(BaseModel):
    date: str
    tool: str
    suggestions_shown: int
    suggestions_accepted: int
    lines_accepted: int
    active_users: int
    cost_usd: float


@router.get("/impact", response_model=AIImpactResponse)
def get_ai_impact(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
):
    now = datetime.now(timezone.utc)
    end_dt = datetime.fromisoformat(end) if end else now
    start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(days=30)

    session = get_session()
    store = MetricStore(session)
    impact = compute_ai_impact(store, start_dt, end_dt)
    session.close()

    return AIImpactResponse(
        ai_assisted_pr_count=impact.ai_assisted_pr_count,
        non_ai_pr_count=impact.non_ai_pr_count,
        ai_avg_cycle_time_hours=impact.ai_avg_cycle_time_hours,
        non_ai_avg_cycle_time_hours=impact.non_ai_avg_cycle_time_hours,
        ai_avg_review_time_hours=impact.ai_avg_review_time_hours,
        non_ai_avg_review_time_hours=impact.non_ai_avg_review_time_hours,
        ai_revert_rate=impact.ai_revert_rate,
        non_ai_revert_rate=impact.non_ai_revert_rate,
        productivity_change_pct=impact.productivity_change_pct,
        tools=[
            AIToolMetric(
                tool=t.tool,
                total_suggestions_shown=t.total_suggestions_shown,
                total_suggestions_accepted=t.total_suggestions_accepted,
                total_lines_accepted=t.total_lines_accepted,
                active_users=t.active_users,
                acceptance_rate=t.acceptance_rate,
                total_cost_usd=t.total_cost_usd,
            )
            for t in impact.tools
        ],
    )


@router.get("/usage", response_model=list[AIUsageDayResponse])
def get_ai_usage(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    tool: Optional[str] = Query(None),
):
    now = datetime.now(timezone.utc)
    end_dt = datetime.fromisoformat(end) if end else now
    start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(days=30)

    session = get_session()
    store = MetricStore(session)
    metrics = store.ai_usage.get_by_period(start_dt, end_dt, tool=tool)
    session.close()

    return [
        AIUsageDayResponse(
            date=m.date.isoformat() if m.date else "",
            tool=m.tool,
            suggestions_shown=m.suggestions_shown or 0,
            suggestions_accepted=m.suggestions_accepted or 0,
            lines_accepted=m.lines_accepted or 0,
            active_users=m.active_users or 0,
            cost_usd=m.cost_usd or 0,
        )
        for m in metrics
    ]
