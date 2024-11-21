from datetime import datetime
import requests
from rich.table import Table
from rich.console import Console

console = Console()

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
          # Add state filtering here
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
          state {     # Add state information
            name
            type
          }
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
        'issues_completed': 0,
        'issues_in_progress': 0,
        'cycle_time': [],
        'user_contributions': {},
        'priority_breakdown': {
            'Urgent': 0,
            'High': 0,
            'Medium': 0,
            'Low': 0,
            'No Priority': 0
        },
        'state_breakdown': {}
    }

    for issue in all_issues:
        # Track state
        state = issue.get('state', {}).get('name', 'Unknown')
        metrics['state_breakdown'][state] = metrics['state_breakdown'].get(state, 0) + 1

        # More accurate completion check
        if issue['state']['type'] == 'completed':
            metrics['issues_completed'] += 1
            if issue['completedAt'] and issue['createdAt']:
                created_at = datetime.fromisoformat(issue['createdAt'].replace('Z', '+00:00'))
                completed_at = datetime.fromisoformat(issue['completedAt'].replace('Z', '+00:00'))
                cycle_time = (completed_at - created_at).total_seconds() / 3600
                if cycle_time > 0:  # Validate cycle time
                    metrics['cycle_time'].append(cycle_time)
        elif issue['state']['type'] in ['started', 'inProgress']:
            metrics['issues_in_progress'] += 1

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

    # Calculate average cycle time with validation
    if metrics['cycle_time']:
        metrics['average_cycle_time'] = sum(metrics['cycle_time']) / len(metrics['cycle_time'])
        if metrics['average_cycle_time'] < 0:
            metrics['average_cycle_time'] = 0
    else:
        metrics['average_cycle_time'] = 0

    return metrics

def display_linear_metrics(metrics):
    console.print("\n[bold green]Linear Metrics[/]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    table.add_row("Issues Created", str(metrics['issues_created']))
    table.add_row("Issues Completed", str(metrics['issues_completed']))
    table.add_row("Issues In Progress", str(metrics['issues_in_progress']))
    if metrics['average_cycle_time'] > 0:
        table.add_row("Average Cycle Time", f"{metrics['average_cycle_time']:.2f} hours ({metrics['average_cycle_time']/24:.1f} days)")
    
    console.print(table)

    # State breakdown
    if metrics['state_breakdown']:
        console.print("\n[bold magenta]Issues by State:[/]")
        state_table = Table(show_header=True, header_style="bold magenta")
        state_table.add_column("State", style="cyan")
        state_table.add_column("Count", justify="right")
        
        for state, count in metrics['state_breakdown'].items():
            state_table.add_row(state, str(count))
        console.print(state_table)

    # Priority breakdown
    if metrics['priority_breakdown']:
        console.print("\n[bold magenta]Issues by Priority:[/]")
        priority_table = Table(show_header=True, header_style="bold magenta")
        priority_table.add_column("Priority", style="cyan")
        priority_table.add_column("Count", justify="right")
        
        for priority, count in metrics['priority_breakdown'].items():
            priority_table.add_row(priority, str(count))
        console.print(priority_table)

    # User contributions
    if metrics['user_contributions']:
        console.print("\n[bold magenta]User Contributions:[/]")
        user_table = Table(show_header=True, header_style="bold magenta")
        user_table.add_column("User", style="cyan")
        user_table.add_column("Created", justify="right")
        user_table.add_column("Completed", justify="right")
        
        for user, contribution in metrics['user_contributions'].items():
            user_table.add_row(
                user,
                str(contribution['created']),
                str(contribution.get('completed', 0))
            )
        console.print(user_table)

