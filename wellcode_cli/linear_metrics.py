import os
from datetime import datetime
import requests
from colorama import Fore, Style
from .utils import color_print

# Import configuration
try:
    from .config import LINEAR_API_KEY
except ImportError:
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

LINEAR_API_ENDPOINT = "https://api.linear.app/graphql"

def get_linear_metrics(start_date, end_date, user_filter=None):
    headers = {
        "Authorization": LINEAR_API_KEY,
        "Content-Type": "application/json"
    }

    # Define your GraphQL query
    query = """
    query ($after: String) {
      issues(
        first: 100
        after: $after
        filter: {
          createdAt: { gte: "%s", lte: "%s" }
        }
      ) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          title
          createdAt
          completedAt
          priority
          assignee {
            id
            name
          }
        }
      }
    }
    """ % (start_date.isoformat(), end_date.isoformat())

    all_issues = []
    has_next_page = True
    after = None

    while has_next_page:
        variables = {"after": after} if after else {}
        response = requests.post(LINEAR_API_ENDPOINT, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()

        if 'errors' in data:
            print("Error in Linear API response:", data['errors'])
            return None

        issues_data = data['data']['issues']
        all_issues.extend(issues_data['nodes'])
        has_next_page = issues_data['pageInfo']['hasNextPage']
        after = issues_data['pageInfo']['endCursor']

    metrics = {
        'issues_created': len(all_issues),
        'issues_completed': sum(1 for issue in all_issues if issue['completedAt']),
        'cycle_time': [],
        'user_contributions': {},
        'priority_breakdown': {
            'Urgent': 0,
            'High': 0,
            'Medium': 0,
            'Low': 0,
            'No Priority': 0
        }
    }

    for issue in all_issues:
        if issue['completedAt']:
            created_at = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
            completed_at = datetime.fromisoformat(issue['completedAt'].replace('Z', '+00:00'))
            cycle_time = (completed_at - created_at).total_seconds() / 3600  # in hours
            metrics['cycle_time'].append(cycle_time)

        if issue['assignee']:
            user = issue['assignee']['name']
            if user not in metrics['user_contributions']:
                metrics['user_contributions'][user] = {'created': 0, 'completed': 0}
            metrics['user_contributions'][user]['created'] += 1
            if issue['completedAt']:
                metrics['user_contributions'][user]['completed'] += 1

        priority = issue.get('priority')
        if priority == 0:
            metrics['priority_breakdown']['No Priority'] += 1
        elif priority == 1:
            metrics['priority_breakdown']['Urgent'] += 1
        elif priority == 2:
            metrics['priority_breakdown']['High'] += 1
        elif priority == 3:
            metrics['priority_breakdown']['Medium'] += 1
        elif priority == 4:
            metrics['priority_breakdown']['Low'] += 1

    if metrics['cycle_time']:
        metrics['average_cycle_time'] = sum(metrics['cycle_time']) / len(metrics['cycle_time'])
    else:
        metrics['average_cycle_time'] = 0

    return metrics

def print_linear_metrics(metrics):
    color_print("\nLINEAR METRICS:", Fore.GREEN, Style.BRIGHT)
    color_print("===============", Fore.GREEN)
    
     
    color_print(f"Issues Created: {metrics['issues_created']}", Fore.CYAN)
    color_print(f"Issues Completed: {metrics['issues_completed']}", Fore.CYAN)
    
    if 'average_cycle_time' in metrics:
        color_print(f"Average Cycle Time: {metrics['average_cycle_time']:.2f} hours", Fore.CYAN)
    
    color_print("\nIssues Created by Priority:", Fore.YELLOW, Style.BRIGHT)
    color_print("---------------------------", Fore.YELLOW)
    for priority, count in metrics['priority_breakdown'].items():
        color_print(f"{priority:12} {count:3d}", Fore.WHITE)
    
    color_print("\nUser Contributions:", Fore.MAGENTA, Style.BRIGHT)
    color_print("-------------------", Fore.MAGENTA)
    for user, contribution in metrics['user_contributions'].items():
        color_print(f"{user:20} Created: {contribution['created']:3d}  Completed: {contribution['completed']:3d}", Fore.WHITE)
    
    color_print("\nTop 5 Users by Issues Created:", Fore.BLUE, Style.BRIGHT)
    color_print("-------------------------------", Fore.BLUE)
    sorted_users = sorted(metrics['user_contributions'].items(), 
                          key=lambda x: x[1]['created'], reverse=True)[:5]
    for user, contribution in sorted_users:
        color_print(f"{user:20} Issues: {contribution['created']:3d}", Fore.WHITE)

    if 'cycle_time' in metrics and metrics['cycle_time']:
        color_print("\nCycle Time Statistics (in hours):", Fore.RED, Style.BRIGHT)
        color_print("----------------------------------", Fore.RED)
        cycle_times = metrics['cycle_time']
        color_print(f"Minimum: {min(cycle_times):.2f}", Fore.WHITE)
        color_print(f"Maximum: {max(cycle_times):.2f}", Fore.WHITE)
        color_print(f"Average: {sum(cycle_times) / len(cycle_times):.2f}", Fore.WHITE)
        
    color_print("\n" + "=" * 40, Fore.GREEN)