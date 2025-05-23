import logging
import base64
from datetime import datetime, timedelta
from typing import Optional

import requests
from rich.console import Console

from ..config import get_jira_api_key, get_jira_domain, get_jira_email
from .models.metrics import JiraOrgMetrics, ProjectMetrics

console = Console()

logger = logging.getLogger(__name__)


def get_jira_metrics(start_date, end_date, user_filter=None) -> Optional[JiraOrgMetrics]:
    """Get Jira metrics for the specified date range"""
    
    # Get configuration
    api_key = get_jira_api_key()
    domain = get_jira_domain()
    email = get_jira_email()
    
    if not all([api_key, domain, email]):
        logger.error("Jira configuration incomplete. Missing API key, domain, or email.")
        return None

    # Create authentication header
    auth_string = f"{email}:{api_key}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    base_url = f"https://{domain}.atlassian.net/rest/api/3"
    
    org_metrics = JiraOrgMetrics(name=domain)

    try:
        # Build JQL query for date range
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")
        
        jql_query = f"created >= '{start_date_str}' AND created <= '{end_date_str}'"
        
        # Add user filter if specified
        if user_filter:
            jql_query += f" AND assignee = '{user_filter}'"

        # Get all issues with pagination
        all_issues = []
        start_at = 0
        max_results = 100
        total_issues = None

        while total_issues is None or start_at < total_issues:
            search_url = f"{base_url}/search"
            params = {
                "jql": jql_query,
                "startAt": start_at,
                "maxResults": max_results,
                "fields": [
                    "summary",
                    "status",
                    "issuetype",
                    "priority",
                    "assignee",
                    "project",
                    "created",
                    "resolutiondate",
                    "components",
                    "fixVersions",
                    "customfield_10016",  # Story Points (common field ID)
                    "timeoriginalestimate",
                    "timespent",
                    "worklog"
                ]
            }

            response = requests.get(search_url, headers=headers, params=params, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"Jira API error: {response.status_code} - {response.text}")
                return None

            data = response.json()
            
            if total_issues is None:
                total_issues = data.get("total", 0)
                console.print(f"Found {total_issues} issues to process...")

            issues = data.get("issues", [])
            all_issues.extend(issues)
            
            start_at += max_results
            
            if len(issues) < max_results:
                break

        console.print(f"Processing {len(all_issues)} issues...")

        # Process all issues
        for issue in all_issues:
            # Update issue metrics
            org_metrics.issues.update_from_issue(issue)

            # Update cycle time metrics
            org_metrics.cycle_time.update_from_issue(issue)

            # Calculate actual time for estimation metrics
            actual_time = calculate_actual_time(issue)
            if actual_time > 0:
                org_metrics.estimation.update_from_issue(issue, actual_time)

            # Update project metrics
            project_data = issue.get("fields", {}).get("project", {})
            if project_data:
                project_key = project_data.get("key")
                project_name = project_data.get("name", "")
                
                if project_key not in org_metrics.projects:
                    # Get additional project details
                    project_details = get_project_details(base_url, headers, project_key)
                    org_metrics.projects[project_key] = ProjectMetrics(
                        key=project_key,
                        name=project_name,
                        lead=project_details.get("lead"),
                        project_type=project_details.get("projectTypeKey")
                    )
                
                org_metrics.projects[project_key].update_from_issue(issue)

            # Update component metrics
            components = issue.get("fields", {}).get("components", [])
            for component in components:
                component_name = component.get("name", "")
                if component_name:
                    if component_name not in org_metrics.component_counts:
                        org_metrics.component_counts[component_name] = 0
                    org_metrics.component_counts[component_name] += 1

            # Update version metrics
            fix_versions = issue.get("fields", {}).get("fixVersions", [])
            for version in fix_versions:
                version_name = version.get("name", "")
                if version_name:
                    if version_name not in org_metrics.version_counts:
                        org_metrics.version_counts[version_name] = 0
                    org_metrics.version_counts[version_name] += 1

        # Aggregate metrics after processing all issues
        org_metrics.aggregate_metrics()

        return org_metrics

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while fetching Jira metrics: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error while fetching Jira metrics: {str(e)}")
        return None


def get_project_details(base_url: str, headers: dict, project_key: str) -> dict:
    """Get additional project details from Jira API"""
    try:
        project_url = f"{base_url}/project/{project_key}"
        response = requests.get(project_url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            project_data = response.json()
            return {
                "lead": project_data.get("lead", {}).get("displayName"),
                "projectTypeKey": project_data.get("projectTypeKey"),
                "description": project_data.get("description", ""),
            }
    except Exception as e:
        logger.warning(f"Could not fetch project details for {project_key}: {str(e)}")
    
    return {}


def calculate_actual_time(issue: dict) -> float:
    """Calculate actual time spent on an issue in hours"""
    fields = issue.get("fields", {})
    
    # Try to get time spent from the issue
    time_spent = fields.get("timespent")  # Time in seconds
    if time_spent:
        return time_spent / 3600  # Convert to hours

    # If no time spent recorded, try to estimate from worklogs
    try:
        # Note: This would require additional API call to get worklogs
        # For now, we'll use a simple estimation based on resolution time
        created = fields.get("created")
        resolved = fields.get("resolutiondate")
        
        if created and resolved:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            resolved_dt = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
            
            # Calculate business hours between dates (rough estimation)
            total_hours = (resolved_dt - created_dt).total_seconds() / 3600
            
            # Estimate actual work time as 25% of total time (accounting for weekends, etc.)
            estimated_work_hours = total_hours * 0.25
            
            return max(0.5, min(estimated_work_hours, 40))  # Cap between 0.5 and 40 hours
            
    except (ValueError, TypeError):
        pass
    
    return 0


def calculate_work_hours(start_date: datetime, end_date: datetime) -> float:
    """Calculate work hours between two dates, excluding weekends"""
    if not start_date or not end_date:
        return 0

    total_hours = 0
    current_date = start_date

    while current_date < end_date:
        if current_date.weekday() < 5:  # Monday to Friday
            day_end = min(
                current_date.replace(hour=17, minute=0, second=0, microsecond=0),
                end_date,
            )
            day_start = max(
                current_date.replace(hour=9, minute=0, second=0, microsecond=0),
                start_date,
            )

            if day_end > day_start:
                work_hours = (day_end - day_start).total_seconds() / 3600
                total_hours += min(8, work_hours)  # Cap at 8 hours per day

        current_date = current_date.replace(
            hour=9, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)

    return total_hours


def get_jira_projects(domain: str, email: str, api_key: str) -> list:
    """Get list of accessible Jira projects"""
    auth_string = f"{email}:{api_key}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json"
    }

    try:
        url = f"https://{domain}.atlassian.net/rest/api/3/project"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch projects: {response.status_code}")
            return []
            
    except Exception as e:
        logger.error(f"Error fetching Jira projects: {str(e)}")
        return []


def test_jira_connection(domain: str, email: str, api_key: str) -> bool:
    """Test Jira connection with provided credentials"""
    auth_string = f"{email}:{api_key}"
    auth_bytes = auth_string.encode('ascii')
    auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json"
    }

    try:
        url = f"https://{domain}.atlassian.net/rest/api/3/myself"
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            console.print(f"[green]✓ Connected to Jira as {user_data.get('displayName', email)}[/]")
            return True
        else:
            console.print(f"[red]✗ Jira connection failed: {response.status_code}[/]")
            return False
            
    except Exception as e:
        console.print(f"[red]✗ Jira connection error: {str(e)}[/]")
        return False 