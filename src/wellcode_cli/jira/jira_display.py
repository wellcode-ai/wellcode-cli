import statistics
from datetime import datetime, timezone

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel

console = Console()


def format_time(hours: float) -> str:
    """Format time in hours to a human-readable string"""
    if hours < 1:
        return f"{hours * 60:.0f}m"
    elif hours < 24:
        return f"{hours:.1f}h"
    else:
        days = hours / 24
        return f"{days:.1f}d"


def display_jira_metrics(org_metrics):
    """Display Jira metrics with a modern UI using Rich components."""
    # Header with organization info and time range
    now = datetime.now(timezone.utc)
    console.print(
        Panel(
            "[bold cyan]Jira Engineering Analytics[/]\n"
            + f"[dim]Organization: {org_metrics.name}[/]\n"
            + f"[dim]Report Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC[/]",
            box=ROUNDED,
            style="cyan",
        )
    )

    # 1. Core Issue Metrics with health indicators
    total_issues = org_metrics.issues.total_created
    completed_issues = org_metrics.issues.total_completed
    completion_rate = (completed_issues / total_issues * 100) if total_issues > 0 else 0

    health_indicator = (
        "🟢" if completion_rate > 80 else "🟡" if completion_rate > 60 else "🔴"
    )

    console.print(
        Panel(
            f"{health_indicator} [bold green]Issues Created:[/] {total_issues}\n"
            + f"[bold yellow]Issues Completed:[/] {completed_issues} ({completion_rate:.1f}% completion rate)\n"
            + f"[bold red]Bugs Created:[/] {org_metrics.issues.bugs_created}\n"
            + f"[bold blue]Stories Created:[/] {org_metrics.issues.stories_created}\n"
            + f"[bold magenta]Tasks Created:[/] {org_metrics.issues.tasks_created}\n"
            + f"[bold cyan]Epics Created:[/] {org_metrics.issues.epics_created}",
            title="[bold]Issue Flow",
            box=ROUNDED,
        )
    )

    # 2. Time Metrics with visual indicators
    cycle = org_metrics.cycle_time
    avg_cycle_time = statistics.mean(cycle.cycle_times) if cycle.cycle_times else 0
    cycle_health = (
        "🟢" if avg_cycle_time < 24 else "🟡" if avg_cycle_time < 72 else "🔴"
    )

    console.print(
        Panel(
            f"{cycle_health} [bold]Average Cycle Time:[/] {format_time(avg_cycle_time)}\n"
            + f"[bold]Median Cycle Time:[/] {format_time(statistics.median(cycle.cycle_times) if cycle.cycle_times else 0)}\n"
            + f"[bold]95th Percentile:[/] {format_time(cycle.get_stats()['p95_cycle_time'])}\n"
            + f"[bold]Average Resolution Time:[/] {format_time(statistics.mean(cycle.resolution_times) if cycle.resolution_times else 0)}",
            title="[bold blue]Time Metrics",
            box=ROUNDED,
        )
    )

    # 3. Estimation Accuracy
    est = org_metrics.estimation
    if est.total_estimated > 0:
        accuracy_rate = est.accurate_estimates / est.total_estimated * 100
        accuracy_health = (
            "🟢" if accuracy_rate > 80 else "🟡" if accuracy_rate > 60 else "🔴"
        )

        console.print(
            Panel(
                f"{accuracy_health} [bold]Estimation Accuracy:[/] {accuracy_rate:.1f}%\n"
                + f"[bold green]Accurate Estimates:[/] {est.accurate_estimates}\n"
                + f"[bold red]Underestimates:[/] {est.underestimates}\n"
                + f"[bold yellow]Overestimates:[/] {est.overestimates}\n"
                + f"[bold]Average Variance:[/] {statistics.mean(est.estimation_variance) if est.estimation_variance else 0:.1f}%",
                title="[bold yellow]Estimation Health",
                box=ROUNDED,
            )
        )

    # 4. Project Performance
    if org_metrics.projects:
        project_panels = []
        for project_key, project in org_metrics.projects.items():
            completion_rate = (
                (project.completed_issues / project.total_issues * 100)
                if project.total_issues > 0
                else 0
            )
            project_health = (
                "🟢" if completion_rate > 80 else "🟡" if completion_rate > 60 else "🔴"
            )

            project_panels.append(
                f"{project_health} [bold cyan]{project.name} ({project_key})[/]\n"
                + f"Issues: {project.total_issues} total, {project.completed_issues} completed ({completion_rate:.1f}%)\n"
                + f"Bugs: {project.bugs_count} | Stories: {project.stories_count} | Tasks: {project.tasks_count} | Epics: {project.epics_count}\n"
                + f"Assignees: {len(project.assignees_involved)}\n"
                + f"Lead: {project.lead or 'Not set'} | Type: {project.project_type or 'Unknown'}"
            )

        console.print(
            Panel(
                "\n\n".join(project_panels),
                title="[bold magenta]Project Health",
                box=ROUNDED,
            )
        )

    # 5. Priority Distribution
    if org_metrics.issues.by_priority:
        display_priority_distribution(org_metrics.issues.by_priority)

    # 6. Assignee Performance
    if org_metrics.issues.by_assignee:
        display_assignee_performance(org_metrics.issues.by_assignee, org_metrics.cycle_time.by_assignee)

    # 7. Component and Version Distribution
    if org_metrics.component_counts or org_metrics.version_counts:
        display_component_version_summary(org_metrics.component_counts, org_metrics.version_counts)


def display_priority_distribution(priority_counts):
    """Display a visual summary of issue priorities."""
    if not priority_counts:
        return

    # Sort priorities by count in descending order
    sorted_priorities = sorted(priority_counts.items(), key=lambda x: x[1], reverse=True)

    # Calculate the maximum count for scaling
    max_count = max(count for _, count in sorted_priorities)
    max_bar_length = 30  # Maximum length of the bar in characters

    # Create the priority summary
    priority_lines = []
    for priority, count in sorted_priorities:
        # Calculate bar length proportional to count
        bar_length = int((count / max_count) * max_bar_length)
        bar = "█" * bar_length

        # Choose color based on priority name
        color = (
            "red"
            if "highest" in priority.lower() or "critical" in priority.lower()
            else (
                "yellow"
                if "high" in priority.lower()
                else "blue" if "medium" in priority.lower() else "green"
            )
        )

        priority_lines.append(f"[{color}]{priority:<15}[/] {bar} ({count})")

    console.print(
        Panel(
            "\n".join(priority_lines), title="[bold cyan]Priority Distribution", box=ROUNDED
        )
    )


def display_assignee_performance(assignee_counts, assignee_cycle_times):
    """Display assignee performance metrics."""
    if not assignee_counts:
        return

    # Sort assignees by issue count in descending order
    sorted_assignees = sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True)

    # Take top 10 assignees
    top_assignees = sorted_assignees[:10]

    assignee_lines = []
    for assignee, count in top_assignees:
        avg_cycle_time = 0
        if assignee in assignee_cycle_times and assignee_cycle_times[assignee]:
            avg_cycle_time = statistics.mean(assignee_cycle_times[assignee])

        # Performance indicator based on cycle time
        performance_indicator = (
            "🟢" if avg_cycle_time < 24 else "🟡" if avg_cycle_time < 72 else "🔴"
        )

        assignee_lines.append(
            f"{performance_indicator} [bold]{assignee:<20}[/] Issues: {count:>3} | Avg Cycle: {format_time(avg_cycle_time)}"
        )

    console.print(
        Panel(
            "\n".join(assignee_lines),
            title="[bold green]Top Assignee Performance",
            box=ROUNDED,
        )
    )


def display_component_version_summary(component_counts, version_counts):
    """Display a summary of components and versions."""
    panels = []

    if component_counts:
        # Sort components by count in descending order
        sorted_components = sorted(component_counts.items(), key=lambda x: x[1], reverse=True)
        top_components = sorted_components[:5]  # Top 5 components

        component_lines = []
        for component, count in top_components:
            component_lines.append(f"[cyan]{component:<25}[/] ({count})")

        panels.append(
            Panel(
                "\n".join(component_lines),
                title="[bold cyan]Top Components",
                box=ROUNDED,
            )
        )

    if version_counts:
        # Sort versions by count in descending order
        sorted_versions = sorted(version_counts.items(), key=lambda x: x[1], reverse=True)
        top_versions = sorted_versions[:5]  # Top 5 versions

        version_lines = []
        for version, count in top_versions:
            version_lines.append(f"[magenta]{version:<25}[/] ({count})")

        panels.append(
            Panel(
                "\n".join(version_lines),
                title="[bold magenta]Top Fix Versions",
                box=ROUNDED,
            )
        )

    # Display panels side by side if both exist
    if len(panels) == 2:
        from rich.columns import Columns
        console.print(Columns(panels))
    elif panels:
        console.print(panels[0]) 