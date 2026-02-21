import logging

import rich_click as click
from rich.console import Console

from wellcode_cli import __version__

from .commands import chat, chat_interface, completion, config, report, review

click.rich_click.USE_RICH_MARKUP = True
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_ERRORS_SUGGESTION = "yellow italic"
click.rich_click.ERRORS_SUGGESTION = "Try '--help' for more information."

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="wellcode")
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="Increase verbosity (can be used multiple times)",
)
@click.pass_context
def cli(ctx, verbose):
    """Wellcode - Open-source developer productivity platform"""
    if verbose == 0:
        log_level = logging.WARNING
    elif verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    logging.basicConfig(level=log_level, format="%(levelname)s:%(message)s")

    if ctx.invoked_subcommand is None:
        ctx.invoke(chat_interface)


# Existing commands
cli.add_command(review)
cli.add_command(config)
cli.add_command(chat_interface, name="chat")
cli.add_command(chat)
cli.add_command(report)
cli.add_command(completion)


# --- New commands ---

@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", "-p", default=8787, help="Port to listen on")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--schedule/--no-schedule", default=True, help="Enable background metric collection")
@click.option("--interval", default=6, help="Collection interval in hours")
def serve(host, port, reload, schedule, interval):
    """Start the Wellcode API server and web dashboard."""
    import uvicorn
    from .db.engine import init_db

    init_db()

    if schedule:
        from .workers.scheduler import start_scheduler
        start_scheduler(interval_hours=interval)
        console.print(f"[green]Background collection enabled (every {interval}h)[/]")

    console.print(f"\n[bold blue]Wellcode[/] v{__version__}")
    console.print(f"[green]API server starting at http://{host}:{port}[/]")
    console.print(f"[dim]API docs at http://{host}:{port}/docs[/]\n")

    uvicorn.run(
        "wellcode_cli.api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


@cli.command()
@click.option("--start-date", "-s", type=click.DateTime(), help="Start date (YYYY-MM-DD)")
@click.option("--end-date", "-e", type=click.DateTime(), help="End date (YYYY-MM-DD)")
@click.option("--days", "-d", default=7, help="Number of days to look back (default: 7)")
def collect(start_date, end_date, days):
    """Collect metrics from all configured providers and store them."""
    from datetime import datetime, timedelta, timezone
    from .db.engine import init_db
    from .services.collector import collect_all

    init_db()

    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=days)

    console.print(f"\n[bold blue]Wellcode[/] - Collecting metrics")
    console.print(f"Period: {start_date.date()} to {end_date.date()}\n")

    with console.status("[bold green]Collecting metrics from all providers..."):
        summary = collect_all(start_date, end_date)

    if "error" in summary:
        console.print(f"[red]Error: {summary['error']}[/]")
        return

    console.print("[bold green]Collection complete![/]\n")
    console.print(f"  Providers: {len(summary.get('providers', []))}")
    console.print(f"  Pull Requests: {summary.get('total_prs', 0)}")
    console.print(f"  Deployments: {summary.get('total_deployments', 0)}")
    console.print(f"  Repositories: {summary.get('total_repos', 0)}")

    for prov in summary.get("providers", []):
        status = "[green]OK[/]" if "error" not in prov else f"[red]{prov['error']}[/]"
        console.print(f"  [{prov['name']}] PRs: {prov['prs']}, Deploys: {prov['deployments']} {status}")


@cli.command()
@click.option("--start-date", "-s", type=click.DateTime(), help="Start date (YYYY-MM-DD)")
@click.option("--end-date", "-e", type=click.DateTime(), help="End date (YYYY-MM-DD)")
@click.option("--days", "-d", default=30, help="Number of days to analyze (default: 30)")
@click.option("--repo-id", type=int, help="Filter by repository ID")
@click.option("--team-id", type=int, help="Filter by team ID")
def dora(start_date, end_date, days, repo_id, team_id):
    """View DORA metrics for your organization."""
    from datetime import datetime, timedelta, timezone
    from rich.panel import Panel
    from rich.table import Table
    from .db.engine import init_db, get_session
    from .db.repository import MetricStore
    from .services.dora import compute_dora, DORA_THRESHOLDS

    init_db()

    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=days)

    session = get_session()
    store = MetricStore(session)
    metrics = compute_dora(store, start_date, end_date, repo_id=repo_id, team_id=team_id)
    session.close()

    level_colors = {"elite": "green", "high": "blue", "medium": "yellow", "low": "red"}
    level_color = level_colors.get(metrics.level, "white")

    console.print(Panel.fit(
        f"[bold {level_color}]DORA Level: {metrics.level.upper()}[/]",
        title="[bold]DORA Metrics",
        subtitle=f"{start_date.date()} to {end_date.date()}",
    ))

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_column("Elite")
    table.add_column("High")
    table.add_column("Medium")

    df = metrics.deployment_frequency
    df_label = f"{df:.2f}/day" if df >= 1 else f"{df * 7:.1f}/week"
    table.add_row("Deployment Frequency", df_label, ">1/day", "weekly-daily", "monthly-weekly")

    lt = metrics.lead_time_hours
    lt_label = f"{lt:.1f}h" if lt < 24 else f"{lt/24:.1f}d"
    table.add_row("Lead Time for Changes", lt_label, "<1h", "<1 day", "<1 week")

    cfr = metrics.change_failure_rate
    table.add_row("Change Failure Rate", f"{cfr*100:.1f}%", "0-15%", "16-30%", "31-45%")

    mttr = metrics.mttr_hours
    mttr_label = f"{mttr:.1f}h" if mttr < 24 else f"{mttr/24:.1f}d"
    table.add_row("Mean Time to Recovery", mttr_label, "<1h", "<1 day", "<1 week")

    console.print(table)

    details = metrics.details
    console.print(f"\n[dim]Deployments: {details['total_deployments']} | "
                  f"Merged PRs: {details['total_merged_prs']} | "
                  f"Reverts: {details['reverts']} | "
                  f"Incidents: {details['incidents']}[/]")


@cli.command(name="ai-metrics")
@click.option("--start-date", "-s", type=click.DateTime(), help="Start date")
@click.option("--end-date", "-e", type=click.DateTime(), help="End date")
@click.option("--days", "-d", default=30, help="Days to analyze")
def ai_metrics_cmd(start_date, end_date, days):
    """View AI coding tool adoption and impact metrics."""
    from datetime import datetime, timedelta, timezone
    from rich.panel import Panel
    from rich.table import Table
    from .db.engine import init_db, get_session
    from .db.repository import MetricStore
    from .services.ai_metrics import compute_ai_impact

    init_db()

    if end_date is None:
        end_date = datetime.now(timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=days)

    session = get_session()
    store = MetricStore(session)
    impact = compute_ai_impact(store, start_date, end_date)
    session.close()

    total = impact.ai_assisted_pr_count + impact.non_ai_pr_count
    ai_pct = (impact.ai_assisted_pr_count / total * 100) if total > 0 else 0

    console.print(Panel.fit(
        f"AI-assisted PRs: [bold]{impact.ai_assisted_pr_count}[/] ({ai_pct:.1f}% of total)\n"
        f"Non-AI PRs: {impact.non_ai_pr_count}\n"
        f"Productivity change: [bold]{'+'if impact.productivity_change_pct>0 else ''}{impact.productivity_change_pct:.1f}%[/]",
        title="[bold blue]AI Impact Analysis",
    ))

    if impact.tools:
        table = Table(title="AI Tool Usage", show_header=True, header_style="bold")
        table.add_column("Tool")
        table.add_column("Active Users")
        table.add_column("Suggestions")
        table.add_column("Accepted")
        table.add_column("Acceptance Rate")
        table.add_column("Lines Accepted")
        table.add_column("Cost (USD)")

        for t in impact.tools:
            table.add_row(
                t.tool,
                str(t.active_users),
                str(t.total_suggestions_shown),
                str(t.total_suggestions_accepted),
                f"{t.acceptance_rate*100:.1f}%",
                str(t.total_lines_accepted),
                f"${t.total_cost_usd:.2f}",
            )
        console.print(table)

    if impact.ai_avg_cycle_time_hours > 0 or impact.non_ai_avg_cycle_time_hours > 0:
        table2 = Table(title="AI vs Non-AI Comparison", show_header=True, header_style="bold")
        table2.add_column("Metric")
        table2.add_column("AI-Assisted")
        table2.add_column("Non-AI")

        table2.add_row(
            "Avg Cycle Time",
            f"{impact.ai_avg_cycle_time_hours:.1f}h",
            f"{impact.non_ai_avg_cycle_time_hours:.1f}h",
        )
        table2.add_row(
            "Avg Review Time",
            f"{impact.ai_avg_review_time_hours:.1f}h",
            f"{impact.non_ai_avg_review_time_hours:.1f}h",
        )
        table2.add_row(
            "Revert Rate",
            f"{impact.ai_revert_rate*100:.1f}%",
            f"{impact.non_ai_revert_rate*100:.1f}%",
        )
        console.print(table2)


@cli.command()
@click.option("--template", "-t", type=click.Choice(["pulse", "full_dx"]), default="pulse")
@click.option("--title", help="Survey title")
def survey(template, title):
    """Create and manage developer experience surveys."""
    from .db.engine import init_db
    from .services.surveys import create_survey_from_template, SURVEY_TEMPLATES

    init_db()

    s = create_survey_from_template(template=template, title=title)
    console.print(f"\n[green]Survey created:[/] {s.title}")
    console.print(f"  ID: {s.id}")
    console.print(f"  Type: {template}")
    console.print(f"  Questions: {len(SURVEY_TEMPLATES[template])}")
    console.print(f"\n[dim]Share via API: POST /api/v1/surveys/respond[/]")


def main():
    cli()


if __name__ == "__main__":
    main()
