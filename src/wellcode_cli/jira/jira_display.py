import statistics
from datetime import datetime, timezone

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel

console = Console()


def format_time(hours: float) -> str:
    """Convert hours to a human-readable format."""
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    elif hours < 24:
        return f"{round(hours, 1)} hours"
    else:
        days = hours / 24
        return f"{round(days, 1)} days"


def _health_indicator(value: float, good: float, warn: float) -> str:
    if value > good:
        return "🟢"
    if value > warn:
        return "🟡"
    return "🔴"


def _health_indicator_low_good(value: float, good: float, warn: float) -> str:
    """Health indicator where lower values are better (e.g. cycle time)."""
    if value < good:
        return "🟢"
    if value < warn:
        return "🟡"
    return "🔴"


def _safe_mean(values: list) -> float:
    return statistics.mean(values) if values else 0


def _label_color(name: str) -> str:
    lower = name.lower()
    if "bug" in lower:
        return "red"
    if "feature" in lower or "story" in lower:
        return "green"
    if "improvement" in lower:
        return "yellow"
    return "blue"


def display_jira_metrics(org_metrics):
    """Display JIRA metrics with a modern UI using Rich components."""
    now = datetime.now(timezone.utc)
    console.print(
        Panel(
            "[bold cyan]JIRA Engineering Analytics[/]\n"
            + f"[dim]Instance: {org_metrics.name}[/]\n"
            + f"[dim]Report Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC[/]",
            box=ROUNDED,
            style="cyan",
        )
    )

    _display_issue_flow(org_metrics)
    _display_time_metrics(org_metrics)
    _display_sprint_performance(org_metrics)
    _display_estimation_health(org_metrics)
    _display_project_health(org_metrics)

    if org_metrics.label_counts:
        _display_distribution("Label Distribution", dict(org_metrics.label_counts))
    if org_metrics.component_counts:
        _display_distribution("Component Distribution", dict(org_metrics.component_counts))


def _display_issue_flow(org_metrics):
    total = org_metrics.issues.total_created
    completed = org_metrics.issues.total_completed
    completion_rate = (completed / total * 100) if total > 0 else 0
    health = _health_indicator(completion_rate, 80, 60)

    console.print(
        Panel(
            f"{health} [bold green]Issues Created:[/] {total}\n"
            + f"[bold yellow]Issues Completed:[/] {completed} ({completion_rate:.1f}% completion rate)\n"
            + f"[bold red]Bugs Created:[/] {org_metrics.issues.bugs_created}\n"
            + f"[bold blue]Stories Created:[/] {org_metrics.issues.stories_created}\n"
            + f"[bold white]Tasks Created:[/] {org_metrics.issues.tasks_created}",
            title="[bold]Issue Flow",
            box=ROUNDED,
        )
    )


def _display_time_metrics(org_metrics):
    cycle = org_metrics.cycle_time
    avg_cycle_time = _safe_mean(cycle.cycle_times)
    cycle_health = _health_indicator_low_good(avg_cycle_time, 24, 72)

    console.print(
        Panel(
            f"{cycle_health} [bold]Cycle Time:[/] {format_time(avg_cycle_time)}\n"
            + f"[bold]Time to Start:[/] {format_time(_safe_mean(cycle.time_to_start))}\n"
            + f"[bold]Time in Progress:[/] {format_time(_safe_mean(cycle.time_in_progress))}",
            title="[bold blue]Time Metrics",
            box=ROUNDED,
        )
    )


def _display_sprint_performance(org_metrics):
    if not org_metrics.sprints:
        return

    sprint_panels = []
    for sprint in org_metrics.sprints:
        health = _health_indicator(sprint.points_completion_rate, 80, 60)
        goal_line = f"Goal: {sprint.goal}\n" if sprint.goal else ""

        sprint_panels.append(
            f"{health} [bold cyan]{sprint.name}[/] ({sprint.state})\n"
            + goal_line
            + f"Issues: {sprint.completed_issues}/{sprint.total_issues} completed ({sprint.completion_rate:.1f}%)\n"
            + f"Story Points: {sprint.story_points_completed}/{sprint.story_points_committed} ({sprint.points_completion_rate:.1f}%)\n"
            + f"Velocity: {sprint.velocity} points"
        )

    console.print(
        Panel(
            "\n\n".join(sprint_panels),
            title="[bold magenta]Sprint Performance",
            box=ROUNDED,
        )
    )


def _display_estimation_health(org_metrics):
    est = org_metrics.estimation
    if est.total_estimated == 0:
        return

    accuracy_rate = est.accurate_estimates / est.total_estimated * 100
    accuracy_health = _health_indicator(accuracy_rate, 80, 60)
    avg_variance = _safe_mean(est.estimation_variance)

    console.print(
        Panel(
            f"{accuracy_health} [bold]Estimation Accuracy:[/] {accuracy_rate:.1f}%\n"
            + f"[bold green]Accurate Estimates:[/] {est.accurate_estimates}\n"
            + f"[bold red]Underestimates:[/] {est.underestimates}\n"
            + f"[bold yellow]Overestimates:[/] {est.overestimates}\n"
            + f"[bold]Average Variance:[/] {avg_variance:.1f} hours",
            title="[bold yellow]Estimation Health",
            box=ROUNDED,
        )
    )


def _display_project_health(org_metrics):
    if not org_metrics.projects:
        return

    project_panels = []
    for _, project in org_metrics.projects.items():
        completion_rate = (
            (project.completed_issues / project.total_issues * 100)
            if project.total_issues > 0
            else 0
        )
        proj_health = _health_indicator(completion_rate, 80, 50)

        project_panels.append(
            f"{proj_health} [bold cyan]{project.name}[/] ({project.key})\n"
            + f"Issues: {project.total_issues} total, {project.completed_issues} completed ({completion_rate:.1f}%)\n"
            + f"Bugs: {project.bugs_count} | Stories: {project.stories_count} | Tasks: {project.tasks_count}\n"
            + f"Cycle Time: {format_time(project.avg_cycle_time)}\n"
            + f"Team Members: {len(project.members)}"
        )

    console.print(
        Panel(
            "\n\n".join(project_panels),
            title="[bold green]Project Health",
            box=ROUNDED,
        )
    )


def _display_distribution(title: str, counts: dict):
    """Display a visual bar-chart summary of label or component counts."""
    if not counts:
        return

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    max_count = max(count for _, count in sorted_items)
    max_bar_length = 40

    lines = []
    for name, count in sorted_items:
        bar_length = int((count / max_count) * max_bar_length)
        bar = "█" * bar_length
        color = _label_color(name)
        lines.append(f"[{color}]{name:<25}[/] {bar} ({count})")

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]{title}",
            box=ROUNDED,
        )
    )
