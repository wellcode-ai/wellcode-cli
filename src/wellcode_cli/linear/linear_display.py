import statistics
from datetime import datetime, timezone

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel

console = Console()


def format_time(hours: float) -> str:
    """Convert hours to a human-readable format"""
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    elif hours < 24:
        return f"{round(hours, 1)} hours"
    else:
        days = hours / 24
        return f"{round(days, 1)} days"


def display_linear_metrics(org_metrics):
    """Display Linear metrics with a modern UI using Rich components."""
    # Header with organization info and time range
    now = datetime.now(timezone.utc)
    console.print(
        Panel(
            "[bold cyan]Linear Engineering Analytics[/]\n"
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
            + f"[bold blue]Features Created:[/] {org_metrics.issues.features_created}",
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
            f"{cycle_health} [bold]Cycle Time:[/] {format_time(avg_cycle_time)}\n"
            + f"[bold]Time to Start:[/] {format_time(statistics.mean(cycle.time_to_start) if cycle.time_to_start else 0)}\n"
            + f"[bold]Time in Progress:[/] {format_time(statistics.mean(cycle.time_in_progress) if cycle.time_in_progress else 0)}",
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
                + f"[bold]Average Variance:[/] {statistics.mean(est.estimation_variance) if est.estimation_variance else 0:.1f} hours",
                title="[bold yellow]Estimation Health",
                box=ROUNDED,
            )
        )

    # 4. Team Performance
    if org_metrics.teams:
        team_panels = []
        for team_name, team in org_metrics.teams.items():
            completion_rate = (
                (team.issues_completed / team.issues_created * 100)
                if team.issues_created > 0
                else 0
            )
            team_health = (
                "🟢" if completion_rate > 80 else "🟡" if completion_rate > 60 else "🔴"
            )

            team_panels.append(
                f"{team_health} [bold cyan]{team_name}[/]\n"
                + f"Issues: {team.issues_created} created, {team.issues_completed} completed ({completion_rate:.1f}%)\n"
                + f"Cycle Time: {format_time(team.avg_cycle_time)}\n"
                + f"Estimation Accuracy: {team.estimation_accuracy:.1f}%"
            )

        console.print(
            Panel(
                "\n\n".join(team_panels),
                title="[bold green]Team Performance",
                box=ROUNDED,
            )
        )

    # 5. Project Health
    if org_metrics.projects:
        project_panels = []
        for _, project in org_metrics.projects.items():
            progress_indicator = (
                "🟢"
                if project.progress >= 80
                else "🟡" if project.progress >= 50 else "🔴"
            )

            # Calculate project-specific metrics
            completion_rate = (
                (project.completed_issues / project.total_issues * 100)
                if project.total_issues > 0
                else 0
            )

            project_panels.append(
                f"{progress_indicator} [bold cyan]{project.name}[/]\n"
                + f"Progress: {project.progress:.1f}%\n"
                + f"Issues: {project.total_issues} total, {project.completed_issues} completed ({completion_rate:.1f}%)\n"
                + f"Bugs: {project.bugs_count} | Features: {project.features_count}\n"
                + f"Teams Involved: {len(project.teams_involved)}"
            )

        console.print(
            Panel(
                "\n\n".join(project_panels),
                title="[bold magenta]Project Health",
                box=ROUNDED,
            )
        )

    # 6. Label Distribution
    display_label_summary(org_metrics.label_counts)


def display_label_summary(label_counts):
    """Display a visual summary of issue labels."""
    if not label_counts:
        return

    # Sort labels by count in descending order
    sorted_labels = sorted(label_counts.items(), key=lambda x: x[1], reverse=True)

    # Calculate the maximum count for scaling
    max_count = max(count for _, count in sorted_labels)
    max_bar_length = 40  # Maximum length of the bar in characters

    # Create the label summary
    label_lines = []
    for label, count in sorted_labels:
        # Calculate bar length proportional to count
        bar_length = int((count / max_count) * max_bar_length)
        bar = "█" * bar_length

        # Choose color based on label name (you can customize this)
        color = (
            "green"
            if "feature" in label.lower()
            else (
                "red"
                if "bug" in label.lower()
                else "yellow" if "improvement" in label.lower() else "blue"
            )
        )

        label_lines.append(f"[{color}]{label:<20}[/] {bar} ({count})")

    console.print(
        Panel(
            "\n".join(label_lines), title="[bold cyan]Label Distribution", box=ROUNDED
        )
    )
