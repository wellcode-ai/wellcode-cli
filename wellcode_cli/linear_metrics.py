from datetime import datetime, timedelta
import requests
from rich.table import Table
from rich.console import Console
from dateutil import parser
from dateutil import tz

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
          estimate
          startedAt
          state {
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
        'state_breakdown': {},
        'estimation_accuracy': {
            'total_estimated': 0,
            'accurate_estimates': 0,
            'underestimates': 0,
            'overestimates': 0,
            'estimation_variance': [],
            'estimate_unit': 'points'
        }
    }

    # Process basic metrics
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

        # Calculate estimation accuracy for points
        estimate_points = issue.get('estimate')
        started_at = issue.get('startedAt')
        completed_at = issue.get('completedAt')
        
        if estimate_points and started_at and completed_at and issue['state']['type'] == 'completed':
            metrics['estimation_accuracy']['total_estimated'] += 1
            
            try:
                started = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                
                # Calculate working hours between dates
                working_hours = calculate_work_hours(started, completed)
                expected_hours = points_to_expected_hours(estimate_points)
                
                if working_hours == 0:
                    continue
                    
                # Calculate variance percentage
                variance_percent = ((working_hours - expected_hours) / expected_hours) * 100
                metrics['estimation_accuracy']['estimation_variance'].append(variance_percent)
                
                # Categorize accuracy (within 20% is considered accurate)
                if abs(variance_percent) <= 20:
                    metrics['estimation_accuracy']['accurate_estimates'] += 1
                elif variance_percent > 20:
                    metrics['estimation_accuracy']['underestimates'] += 1
                else:
                    metrics['estimation_accuracy']['overestimates'] += 1
                
            except Exception:
                pass

    # Calculate average cycle time with validation
    if metrics['cycle_time']:
        metrics['average_cycle_time'] = sum(metrics['cycle_time']) / len(metrics['cycle_time'])
        if metrics['average_cycle_time'] < 0:
            metrics['average_cycle_time'] = 0
    else:
        metrics['average_cycle_time'] = 0

    # Calculate estimation accuracy
    metrics['estimation_accuracy'] = calculate_estimation_accuracy(all_issues)

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

    # Add Estimation Accuracy section
    if 'estimation_accuracy' in metrics and metrics['estimation_accuracy']['total_estimated'] > 0:
        console.print("\n[bold magenta]Estimation Accuracy (Story Points):[/]")
        estimation_table = Table(show_header=True, header_style="bold magenta")
        estimation_table.add_column("Metric", style="cyan")
        estimation_table.add_column("Value", justify="right")
        
        total = metrics['estimation_accuracy']['total_estimated']
        accurate = metrics['estimation_accuracy']['accurate_estimates']
        under = metrics['estimation_accuracy']['underestimates']
        over = metrics['estimation_accuracy']['overestimates']
        
        estimation_table.add_row(
            "Issues with Point Estimates",
            str(total)
        )
        estimation_table.add_row(
            "Accurate Estimates (±20%)",
            f"{accurate} ({(accurate/total)*100:.1f}%)"
        )
        estimation_table.add_row(
            "Underestimated Issues (>20%)",
            f"{under} ({(under/total)*100:.1f}%)"
        )
        estimation_table.add_row(
            "Overestimated Issues (<-20%)",
            f"{over} ({(over/total)*100:.1f}%)"
        )
        
        if metrics['estimation_accuracy']['estimation_variance']:
            avg_variance = sum(metrics['estimation_accuracy']['estimation_variance']) / len(metrics['estimation_accuracy']['estimation_variance'])
            estimation_table.add_row(
                "Average Point Estimation Variance",
                f"{avg_variance:+.1f}%"
            )
        
        console.print(estimation_table)

def calculate_estimation_accuracy(issues):
    """Calculate estimation accuracy metrics"""
    estimated_issues = [i for i in issues if i.get('estimate') and i.get('startedAt') and i.get('completedAt')]
    
    if not estimated_issues:
        return {
            'total_estimated': 0,
            'accurate_estimates': 0,
            'underestimates': 0,
            'overestimates': 0,
            'estimation_variance': []
        }

    accuracy_metrics = {
        'total_estimated': len(estimated_issues),
        'accurate_estimates': 0,
        'underestimates': 0,
        'overestimates': 0,
        'estimation_variance': []
    }

    for issue in estimated_issues:
        estimate = issue['estimate']
        started_at = issue['startedAt']
        completed_at = issue['completedAt']
        
        try:
            started = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
            completed = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            
            actual_time = calculate_work_hours(started, completed)
            
            if actual_time == 0:
                continue
                
            # Calculate variance percentage
            variance_percent = ((actual_time - estimate) / estimate) * 100
            accuracy_metrics['estimation_variance'].append(variance_percent)
            
            # Categorize accuracy (within 20% is considered accurate)
            if abs(variance_percent) <= 20:
                accuracy_metrics['accurate_estimates'] += 1
            elif variance_percent > 20:
                accuracy_metrics['underestimates'] += 1
            else:
                accuracy_metrics['overestimates'] += 1
            
        except Exception:
            pass

    return accuracy_metrics

def calculate_actual_time(issue):
    """Calculate actual time spent on an issue in hours"""
    if not issue.get('completed_at'):
        return None
        
    # Get all cycle times
    started_at = None
    completed_at = parser.parse(issue['completed_at'])
    
    # Look for the first "In Progress" state
    for cycle in issue.get('cycle_times', []):
        if cycle['state'] == 'In Progress':
            started_at = parser.parse(cycle['started_at'])
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
                end_date
            )
            day_start = current_date.replace(hour=9, minute=0, second=0, microsecond=0)
            
            if day_end > day_start:
                work_hours = (day_end - day_start).total_seconds() / 3600
                total_hours += min(8, work_hours)  # Cap at 8 hours per day
        
        current_date = current_date.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
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
        1: 1,              # 1 point = 1 hour
        2: 4,              # 2 points = half day
        3: HOURS_PER_DAY,  # 3 points = 1 day
        5: HOURS_PER_WEEK, # 5 points = 1 week
        8: HOURS_PER_WEEK + HOURS_PER_DAY * 5,  # 8 points = 10 working days (2 weeks)
        13: HOURS_PER_WEEK * 2,  # 13 points = 2 weeks
    }
    
    return POINT_MAPPING.get(points, 0)

