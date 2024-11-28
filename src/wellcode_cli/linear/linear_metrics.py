from datetime import datetime, timedelta

import requests
from dateutil import parser, tz
from rich.console import Console

from ..config import get_linear_api_key
from .models.metrics import LinearOrgMetrics, ProjectMetrics, TeamMetrics

console = Console()

LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"


def get_linear_metrics(start_date, end_date, user_filter=None) -> LinearOrgMetrics:
    headers = {
        "Authorization": get_linear_api_key(),
        "Content-Type": "application/json",
    }

    org_metrics = LinearOrgMetrics(name="Organization")

    # GraphQL query remains the same as current implementation
    query = """
    query ($after: String) {
      issues(
        filter: {
          createdAt: { gte: "%s", lte: "%s" }
        }
        first: 50
        after: $after
      ) {
        nodes {
          id
          title
          identifier
          state {
            name
            type
          }
          project {
            id
            name
            slugId
            startDate
            targetDate
            progress
          }
          team {
            id
            name
            key
          }
          labels {
            nodes {
              id
              name
            }
          }
          estimate
          startedAt
          completedAt
          createdAt
          updatedAt
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """ % (
        start_date.isoformat(),
        end_date.isoformat(),
    )

    all_issues = []
    has_next_page = True
    after = None

    while has_next_page:
        variables = {"after": after} if after else {}
        response = requests.post(
            LINEAR_API_ENDPOINT,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )
        data = response.json()

        if "errors" in data:
            print("Error in Linear API response:", data["errors"])
            raise RuntimeError(f"Linear API error: {data['errors']}")

        issues_data = data["data"]["issues"]
        all_issues.extend(issues_data["nodes"])
        has_next_page = issues_data["pageInfo"]["hasNextPage"]
        after = issues_data["pageInfo"]["endCursor"]

    # Process all issues
    for issue in all_issues:
        # Update issue metrics
        org_metrics.issues.update_from_issue(issue)

        # Update cycle time metrics
        org_metrics.cycle_time.update_from_issue(issue)

        # Calculate actual time for estimation metrics
        actual_time = 0
        if issue.get("startedAt") and issue.get("completedAt"):
            started_at = datetime.fromisoformat(
                issue["startedAt"].replace("Z", "+00:00")
            )
            completed_at = datetime.fromisoformat(
                issue["completedAt"].replace("Z", "+00:00")
            )
            actual_time = calculate_work_hours(started_at, completed_at)

        # Update estimation metrics
        org_metrics.estimation.update_from_issue(issue, actual_time)

        # Update team metrics
        team = issue.get("team", {})
        if team:
            team_key = team.get("key")
            if team_key not in org_metrics.teams:
                org_metrics.teams[team_key] = TeamMetrics(name=team_key)
            org_metrics.teams[team_key].update_from_issue(issue)

        # Update project metrics
        project = issue.get("project", {})
        if project:
            project_slug = project.get("slugId")
            if project_slug not in org_metrics.projects:
                org_metrics.projects[project_slug] = ProjectMetrics(
                    key=project_slug,
                    name=project.get("name", ""),
                    start_date=project.get("startDate"),
                    target_date=project.get("targetDate"),
                    progress=project.get("progress", 0),
                )
            org_metrics.projects[project_slug].update_from_issue(issue)

        # Update label metrics
        labels = issue.get("labels", {}).get("nodes", [])
        for label in labels:
            label_name = label.get("name", "")
            if label_name:
                if label_name not in org_metrics.label_counts:
                    org_metrics.label_counts[label_name] = 0
                org_metrics.label_counts[label_name] += 1

    # Aggregate metrics after processing all issues
    org_metrics.aggregate_metrics()

    return org_metrics


def calculate_estimation_accuracy(issues):
    """Calculate estimation accuracy metrics"""
    estimated_issues = [
        i
        for i in issues
        if i.get("estimate") and i.get("startedAt") and i.get("completedAt")
    ]

    if not estimated_issues:
        return {
            "total_estimated": 0,
            "accurate_estimates": 0,
            "underestimates": 0,
            "overestimates": 0,
            "estimation_variance": [],
        }

    accuracy_metrics = {
        "total_estimated": len(estimated_issues),
        "accurate_estimates": 0,
        "underestimates": 0,
        "overestimates": 0,
        "estimation_variance": [],
    }

    for issue in estimated_issues:
        estimate = issue["estimate"]
        started_at = issue["startedAt"]
        completed_at = issue["completedAt"]

        try:
            started = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

            actual_time = calculate_work_hours(started, completed)

            if actual_time == 0:
                continue

            # Calculate variance percentage
            variance_percent = ((actual_time - estimate) / estimate) * 100
            accuracy_metrics["estimation_variance"].append(variance_percent)

            # Categorize accuracy (within 20% is considered accurate)
            if abs(variance_percent) <= 20:
                accuracy_metrics["accurate_estimates"] += 1
            elif variance_percent > 20:
                accuracy_metrics["underestimates"] += 1
            else:
                accuracy_metrics["overestimates"] += 1

        except Exception as e:
            # Log the error or handle it more specifically
            console.print(f"Error calculating estimation accuracy: {str(e)}")
            continue

    return accuracy_metrics


def calculate_actual_time(issue):
    """Calculate actual time spent on an issue in hours"""
    if not issue.get("completed_at"):
        return None

    # Get all cycle times
    started_at = None
    completed_at = parser.parse(issue["completed_at"])

    # Look for the first "In Progress" state
    for cycle in issue.get("cycle_times", []):
        if cycle["state"] == "In Progress":
            started_at = parser.parse(cycle["started_at"])
            break

    if not started_at:
        return None

    # Calculate work hours between dates
    work_hours = calculate_work_hours(started_at, completed_at)
    return work_hours


def calculate_work_hours(start_date, end_date):
    """Calculate work hours between two dates, excluding weekends"""
    if not start_date or not end_date:
        return 0

    # Convert to UTC for consistent calculations
    if start_date.tzinfo:
        start_date = start_date.astimezone(tz.UTC)
    if end_date.tzinfo:
        end_date = end_date.astimezone(tz.UTC)

    total_hours = 0
    current_date = start_date

    while current_date < end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            day_end = min(
                current_date.replace(hour=17, minute=0, second=0, microsecond=0),
                end_date,
            )
            day_start = current_date.replace(hour=9, minute=0, second=0, microsecond=0)

            if day_end > day_start:
                work_hours = (day_end - day_start).total_seconds() / 3600
                total_hours += min(8, work_hours)  # Cap at 8 hours per day

        current_date = current_date.replace(
            hour=9, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

    return total_hours


def calculate_work_points(start_date, end_date):
    """Calculate work points based on working days between dates"""
    if not start_date or not end_date:
        return 0

    # Convert to UTC for consistent calculations
    if start_date.tzinfo:
        start_date = start_date.astimezone(tz.UTC)
    if end_date.tzinfo:
        end_date = end_date.astimezone(tz.UTC)

    # Calculate working days (excluding weekends)
    total_points = 0
    current_date = start_date

    while current_date < end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            # Add 1 point per working day
            total_points += 1

        # Move to next day
        current_date = current_date + timedelta(days=1)

    return total_points


def calculate_working_days(start_date, end_date):
    """Calculate number of working days between two dates"""
    if not start_date or not end_date:
        return 0

    # Convert to UTC for consistent calculations
    if start_date.tzinfo:
        start_date = start_date.astimezone(tz.UTC)
    if end_date.tzinfo:
        end_date = end_date.astimezone(tz.UTC)

    working_days = 0
    current_date = start_date.date()  # Use date only for day counting
    end_date = end_date.date()

    while current_date <= end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


def points_to_expected_hours(points):
    """Convert story points to expected working hours using Fibonacci scale mapping"""
    HOURS_PER_DAY = 8
    HOURS_PER_WEEK = 40  # 5 working days

    POINT_MAPPING = {
        1: 1,  # 1 point = 1 hour
        2: 4,  # 2 points = half day
        3: HOURS_PER_DAY,  # 3 points = 1 day
        5: HOURS_PER_WEEK,  # 5 points = 1 week
        8: HOURS_PER_WEEK + HOURS_PER_DAY * 5,  # 8 points = 10 working days (2 weeks)
        13: HOURS_PER_WEEK * 2,  # 13 points = 2 weeks
    }

    return POINT_MAPPING.get(points, 0)
