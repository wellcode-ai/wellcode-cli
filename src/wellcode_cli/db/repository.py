"""Data access layer for all persistent metric storage."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    AIUsageMetric,
    DeploymentMetric,
    Developer,
    DORASnapshot,
    IncidentMetric,
    IssueMetric,
    MetricSnapshot,
    Organization,
    PullRequestMetric,
    Repository,
    Survey,
    SurveyQuestion,
    SurveyResponse,
    Team,
    TeamMember,
)


class BaseRepository:
    def __init__(self, session: Session):
        self.session = session

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()


class OrganizationRepo(BaseRepository):
    def get_or_create(self, name: str, provider: str, **kwargs) -> Organization:
        org = self.session.execute(
            select(Organization).where(Organization.name == name)
        ).scalar_one_or_none()
        if org is None:
            org = Organization(name=name, provider=provider, **kwargs)
            self.session.add(org)
            self.session.flush()
        return org


class RepositoryRepo(BaseRepository):
    def get_or_create(self, full_name: str, provider: str, **kwargs) -> Repository:
        repo = self.session.execute(
            select(Repository).where(
                Repository.full_name == full_name,
                Repository.provider == provider,
            )
        ).scalar_one_or_none()
        if repo is None:
            repo = Repository(
                full_name=full_name, name=full_name.split("/")[-1],
                provider=provider, **kwargs,
            )
            self.session.add(repo)
            self.session.flush()
        return repo


class DeveloperRepo(BaseRepository):
    def get_or_create(self, username: str, provider: str, **kwargs) -> Developer:
        dev = self.session.execute(
            select(Developer).where(
                Developer.username == username,
                Developer.provider == provider,
            )
        ).scalar_one_or_none()
        if dev is None:
            dev = Developer(username=username, provider=provider, **kwargs)
            self.session.add(dev)
            self.session.flush()
        return dev


class TeamRepo(BaseRepository):
    def get_or_create(self, name: str, org_id: Optional[int] = None, **kwargs) -> Team:
        q = select(Team).where(Team.name == name)
        if org_id:
            q = q.where(Team.organization_id == org_id)
        team = self.session.execute(q).scalar_one_or_none()
        if team is None:
            team = Team(name=name, organization_id=org_id, **kwargs)
            self.session.add(team)
            self.session.flush()
        return team


class SnapshotRepo(BaseRepository):
    def create(self, period_start: datetime, period_end: datetime,
               source: str = "all") -> MetricSnapshot:
        snap = MetricSnapshot(
            period_start=period_start,
            period_end=period_end,
            source=source,
            status="running",
        )
        self.session.add(snap)
        self.session.flush()
        return snap

    def complete(self, snapshot: MetricSnapshot, summary: dict,
                 duration_seconds: float):
        snapshot.status = "completed"
        snapshot.summary = summary
        snapshot.duration_seconds = duration_seconds
        self.session.flush()

    def fail(self, snapshot: MetricSnapshot, error: str):
        snapshot.status = "failed"
        snapshot.summary = {"error": error}
        self.session.flush()

    def get_latest(self, source: Optional[str] = None) -> Optional[MetricSnapshot]:
        q = select(MetricSnapshot).order_by(MetricSnapshot.collected_at.desc())
        if source:
            q = q.where(MetricSnapshot.source == source)
        return self.session.execute(q.limit(1)).scalar_one_or_none()

    def list_recent(self, limit: int = 20):
        return self.session.execute(
            select(MetricSnapshot)
            .order_by(MetricSnapshot.collected_at.desc())
            .limit(limit)
        ).scalars().all()


class PullRequestRepo(BaseRepository):
    def upsert(self, pr: PullRequestMetric) -> PullRequestMetric:
        existing = self.session.execute(
            select(PullRequestMetric).where(
                PullRequestMetric.provider == pr.provider,
                PullRequestMetric.external_id == pr.external_id,
            )
        ).scalar_one_or_none()
        if existing:
            for col in PullRequestMetric.__table__.columns:
                if col.name not in ("id", "provider", "external_id"):
                    val = getattr(pr, col.name)
                    if val is not None:
                        setattr(existing, col.name, val)
            self.session.flush()
            return existing
        self.session.add(pr)
        self.session.flush()
        return pr

    def get_by_period(self, start: datetime, end: datetime,
                      repo_id: Optional[int] = None,
                      author_id: Optional[int] = None):
        q = select(PullRequestMetric).where(
            PullRequestMetric.created_at >= start,
            PullRequestMetric.created_at <= end,
        )
        if repo_id:
            q = q.where(PullRequestMetric.repository_id == repo_id)
        if author_id:
            q = q.where(PullRequestMetric.author_id == author_id)
        return self.session.execute(
            q.order_by(PullRequestMetric.created_at)
        ).scalars().all()

    def get_merged_by_period(self, start: datetime, end: datetime,
                             repo_id: Optional[int] = None):
        q = select(PullRequestMetric).where(
            PullRequestMetric.merged_at >= start,
            PullRequestMetric.merged_at <= end,
            PullRequestMetric.state == "merged",
        )
        if repo_id:
            q = q.where(PullRequestMetric.repository_id == repo_id)
        return self.session.execute(q).scalars().all()


class DeploymentRepo(BaseRepository):
    def add(self, deploy: DeploymentMetric) -> DeploymentMetric:
        self.session.add(deploy)
        self.session.flush()
        return deploy

    def get_by_period(self, start: datetime, end: datetime,
                      repo_id: Optional[int] = None,
                      environment: Optional[str] = None):
        q = select(DeploymentMetric).where(
            DeploymentMetric.deployed_at >= start,
            DeploymentMetric.deployed_at <= end,
        )
        if repo_id:
            q = q.where(DeploymentMetric.repository_id == repo_id)
        if environment:
            q = q.where(DeploymentMetric.environment == environment)
        return self.session.execute(
            q.order_by(DeploymentMetric.deployed_at)
        ).scalars().all()


class IncidentRepo(BaseRepository):
    def add(self, incident: IncidentMetric) -> IncidentMetric:
        self.session.add(incident)
        self.session.flush()
        return incident

    def get_by_period(self, start: datetime, end: datetime):
        return self.session.execute(
            select(IncidentMetric).where(
                IncidentMetric.opened_at >= start,
                IncidentMetric.opened_at <= end,
            ).order_by(IncidentMetric.opened_at)
        ).scalars().all()


class AIUsageRepo(BaseRepository):
    def add(self, metric: AIUsageMetric) -> AIUsageMetric:
        self.session.add(metric)
        self.session.flush()
        return metric

    def get_by_period(self, start: datetime, end: datetime,
                      tool: Optional[str] = None):
        q = select(AIUsageMetric).where(
            AIUsageMetric.date >= start,
            AIUsageMetric.date <= end,
        )
        if tool:
            q = q.where(AIUsageMetric.tool == tool)
        return self.session.execute(q.order_by(AIUsageMetric.date)).scalars().all()

    def get_summary(self, start: datetime, end: datetime):
        return self.session.execute(
            select(
                AIUsageMetric.tool,
                func.sum(AIUsageMetric.suggestions_shown).label("total_shown"),
                func.sum(AIUsageMetric.suggestions_accepted).label("total_accepted"),
                func.sum(AIUsageMetric.lines_accepted).label("total_lines"),
                func.max(AIUsageMetric.active_users).label("peak_users"),
                func.sum(AIUsageMetric.cost_usd).label("total_cost"),
            ).where(
                AIUsageMetric.date >= start,
                AIUsageMetric.date <= end,
            ).group_by(AIUsageMetric.tool)
        ).all()


class IssueRepo(BaseRepository):
    def add(self, issue: IssueMetric) -> IssueMetric:
        self.session.add(issue)
        self.session.flush()
        return issue

    def get_by_period(self, start: datetime, end: datetime,
                      provider: Optional[str] = None):
        q = select(IssueMetric).where(
            IssueMetric.created_at >= start,
            IssueMetric.created_at <= end,
        )
        if provider:
            q = q.where(IssueMetric.provider == provider)
        return self.session.execute(q.order_by(IssueMetric.created_at)).scalars().all()


class DORARepo(BaseRepository):
    def save(self, dora: DORASnapshot) -> DORASnapshot:
        self.session.add(dora)
        self.session.flush()
        return dora

    def get_latest(self, team_id: Optional[int] = None,
                   repo_id: Optional[int] = None) -> Optional[DORASnapshot]:
        q = select(DORASnapshot).order_by(DORASnapshot.period_end.desc())
        if team_id:
            q = q.where(DORASnapshot.team_id == team_id)
        if repo_id:
            q = q.where(DORASnapshot.repository_id == repo_id)
        return self.session.execute(q.limit(1)).scalar_one_or_none()

    def get_history(self, limit: int = 30, team_id: Optional[int] = None):
        q = select(DORASnapshot).order_by(DORASnapshot.period_end.desc())
        if team_id:
            q = q.where(DORASnapshot.team_id == team_id)
        return self.session.execute(q.limit(limit)).scalars().all()


class SurveyRepo(BaseRepository):
    def create_survey(self, survey: Survey) -> Survey:
        self.session.add(survey)
        self.session.flush()
        return survey

    def get_active_surveys(self):
        return self.session.execute(
            select(Survey).where(Survey.status == "active")
        ).scalars().all()

    def add_response(self, response: SurveyResponse) -> SurveyResponse:
        self.session.add(response)
        self.session.flush()
        return response

    def get_responses(self, survey_id: int):
        return self.session.execute(
            select(SurveyResponse).where(SurveyResponse.survey_id == survey_id)
        ).scalars().all()


class MetricStore:
    """Unified access to all metric repositories."""

    def __init__(self, session: Session):
        self.session = session
        self.organizations = OrganizationRepo(session)
        self.repositories = RepositoryRepo(session)
        self.developers = DeveloperRepo(session)
        self.teams = TeamRepo(session)
        self.snapshots = SnapshotRepo(session)
        self.pull_requests = PullRequestRepo(session)
        self.deployments = DeploymentRepo(session)
        self.incidents = IncidentRepo(session)
        self.ai_usage = AIUsageRepo(session)
        self.issues = IssueRepo(session)
        self.dora = DORARepo(session)
        self.surveys = SurveyRepo(session)

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()

    def close(self):
        self.session.close()
