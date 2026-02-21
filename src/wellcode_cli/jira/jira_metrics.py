import logging
from datetime import datetime, timedelta
from typing import Optional

from dateutil import tz
from jira import JIRA
from rich.console import Console

from ..config import get_jira_api_token, get_jira_email, get_jira_url
from .models.metrics import (
    JiraOrgMetrics,
    JiraProjectMetrics,
    JiraSprintMetrics,
)

console = Console()
logger = logging.getLogger(__name__)

STORY_POINTS_FIELD = "story_points"
STORY_POINTS_CUSTOM_FIELD = "customfield_10016"

_SEARCH_FIELDS = (
    "summary,issuetype,status,priority,project,assignee,"
    "created,resolutiondate,labels,components,"
    f"{STORY_POINTS_FIELD},{STORY_POINTS_CUSTOM_FIELD}"
)


def _get_jira_client() -> JIRA:
    url = get_jira_url()
    email = get_jira_email()
    token = get_jira_api_token()
    return JIRA(server=url, basic_auth=(email, token))


def _parse_datetime(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _get_story_points(issue) -> float:
    """Extract story points from an issue, trying common field names."""
    fields = issue.fields
    for attr in (STORY_POINTS_FIELD, STORY_POINTS_CUSTOM_FIELD):
        sp = getattr(fields, attr, None)
        if sp is not None:
            return float(sp)
    return 0


def _get_in_progress_date(issue) -> Optional[datetime]:
    """Find the first transition to an 'In Progress' status category from changelog."""
    if not hasattr(issue, "changelog"):
        return None
    for history in issue.changelog.histories:
        for item in history.items:
            if item.field != "status":
                continue
            to_category = getattr(item, "to_category", None)
            to_str = (item.toString or "").lower()
            if to_category == "indeterminate" or "in progress" in to_str:
                return _parse_datetime(history.created)
    return None


def _extract_issue_fields(issue):
    """Pull relevant scalar values from a JIRA issue for metric processing."""
    fields = issue.fields
    return {
        "issue_type": fields.issuetype.name if fields.issuetype else "Task",
        "status_category": (
            fields.status.statusCategory.key
            if fields.status and fields.status.statusCategory
            else "new"
        ),
        "priority": fields.priority.name if fields.priority else "Medium",
        "project_key": fields.project.key if fields.project else "",
        "project_name": fields.project.name if fields.project else "",
        "assignee": fields.assignee.displayName if fields.assignee else None,
        "created_at": _parse_datetime(fields.created),
        "resolution_date": _parse_datetime(fields.resolutiondate),
        "in_progress_date": _get_in_progress_date(issue),
        "story_points": _get_story_points(issue),
        "labels": fields.labels or [],
        "components": fields.components or [],
    }


def _fetch_all_issues(client: JIRA, jql: str) -> list:
    """Paginate through JQL results and return all issues."""
    all_issues = []
    start_at = 0
    max_results = 50

    while True:
        batch = client.search_issues(
            jql,
            startAt=start_at,
            maxResults=max_results,
            expand="changelog",
            fields=_SEARCH_FIELDS,
        )
        all_issues.extend(batch)
        if len(batch) < max_results:
            break
        start_at += max_results

    return all_issues


def _process_issue(org_metrics: JiraOrgMetrics, issue):
    """Process a single JIRA issue into all metric containers."""
    f = _extract_issue_fields(issue)

    org_metrics.issues.update_from_issue(
        issue_type=f["issue_type"],
        status_category=f["status_category"],
        priority=f["priority"],
        project_key=f["project_key"],
        assignee=f["assignee"],
    )

    if f["created_at"]:
        org_metrics.cycle_time.update_from_issue(
            created_at=f["created_at"],
            resolution_date=f["resolution_date"],
            in_progress_date=f["in_progress_date"],
            project_key=f["project_key"],
            priority=f["priority"],
            issue_type=f["issue_type"],
        )

    actual_hours = 0.0
    if f["in_progress_date"] and f["resolution_date"]:
        actual_hours = calculate_work_hours(f["in_progress_date"], f["resolution_date"])
    if f["story_points"] and actual_hours > 0:
        org_metrics.estimation.update_from_issue(
            story_points=f["story_points"],
            actual_hours=actual_hours,
            project_key=f["project_key"],
        )

    _update_project_metrics(org_metrics, f)
    _update_label_component_counts(org_metrics, f)


def _update_project_metrics(org_metrics: JiraOrgMetrics, f: dict):
    project_key = f["project_key"]
    if not project_key:
        return
    if project_key not in org_metrics.projects:
        org_metrics.projects[project_key] = JiraProjectMetrics(
            key=project_key, name=f["project_name"],
        )
    org_metrics.projects[project_key].update_from_issue(
        issue_type=f["issue_type"],
        status_category=f["status_category"],
        assignee=f["assignee"],
    )


def _update_label_component_counts(org_metrics: JiraOrgMetrics, f: dict):
    for label in f["labels"]:
        org_metrics.label_counts[label] += 1
    for component in f["components"]:
        org_metrics.component_counts[component.name] += 1


def get_jira_metrics(start_date, end_date, user_filter=None) -> JiraOrgMetrics:
    """Collect JIRA metrics for the given date range."""
    client = _get_jira_client()
    org_metrics = JiraOrgMetrics(name=get_jira_url() or "JIRA")

    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    jql = f'created >= "{start_str}" AND created <= "{end_str}"'
    if user_filter:
        jql += f' AND assignee = "{user_filter}"'

    all_issues = _fetch_all_issues(client, jql)

    for issue in all_issues:
        _process_issue(org_metrics, issue)

    _collect_sprint_metrics(client, org_metrics, start_date, end_date)
    org_metrics.aggregate_project_cycle_times()

    return org_metrics


def _is_sprint_in_range(sprint, start_date, end_date) -> bool:
    sprint_end = _parse_datetime(getattr(sprint, "endDate", None))
    sprint_start = _parse_datetime(getattr(sprint, "startDate", None))

    if sprint_end and sprint_end < start_date.replace(tzinfo=sprint_end.tzinfo):
        return False
    if sprint_start and sprint_start > end_date.replace(tzinfo=sprint_start.tzinfo):
        return False
    return True


def _get_status_category(issue) -> str:
    status = issue.fields.status
    if status and status.statusCategory:
        return status.statusCategory.key
    return "new"


def _build_sprint_metrics(client: JIRA, sprint) -> Optional[JiraSprintMetrics]:
    sm = JiraSprintMetrics(
        sprint_id=sprint.id,
        name=sprint.name,
        state=sprint.state,
        goal=getattr(sprint, "goal", "") or "",
    )

    try:
        sprint_issues = client.search_issues(
            f"sprint = {sprint.id}",
            maxResults=200,
            fields=f"issuetype,status,{STORY_POINTS_FIELD},{STORY_POINTS_CUSTOM_FIELD}",
        )
    except Exception:
        return None

    for issue in sprint_issues:
        sm.total_issues += 1
        sp = _get_story_points(issue)
        sm.story_points_committed += sp

        if _get_status_category(issue) == "done":
            sm.completed_issues += 1
            sm.story_points_completed += sp

    return sm


def _collect_sprint_metrics(client: JIRA, org_metrics: JiraOrgMetrics,
                            start_date, end_date):
    """Fetch sprint data from all scrum boards."""
    try:
        boards = client.boards(type="scrum", maxResults=50)
    except Exception as e:
        logger.warning("Could not fetch JIRA boards: %s", e)
        return

    for board in boards:
        try:
            sprints = client.sprints(board.id, state="active,closed")
        except Exception:
            continue

        for sprint in sprints:
            if not _is_sprint_in_range(sprint, start_date, end_date):
                continue
            sm = _build_sprint_metrics(client, sprint)
            if sm:
                org_metrics.sprints.append(sm)


def calculate_work_hours(start_date, end_date):
    """Calculate work hours between two dates, excluding weekends."""
    if not start_date or not end_date:
        return 0

    if start_date.tzinfo:
        start_date = start_date.astimezone(tz.UTC)
    if end_date.tzinfo:
        end_date = end_date.astimezone(tz.UTC)

    total_hours = 0
    current_date = start_date

    while current_date < end_date:
        if current_date.weekday() < 5:
            day_end = min(
                current_date.replace(hour=17, minute=0, second=0, microsecond=0),
                end_date,
            )
            day_start = current_date.replace(hour=9, minute=0, second=0, microsecond=0)

            if day_end > day_start:
                work_hours = (day_end - day_start).total_seconds() / 3600
                total_hours += min(8, work_hours)

        current_date = current_date.replace(
            hour=9, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

    return total_hours
